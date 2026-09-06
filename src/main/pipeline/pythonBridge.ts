import { spawn, ChildProcessWithoutNullStreams } from 'child_process'
import { createInterface } from 'readline'
import { join } from 'path'
import { existsSync } from 'fs'
import { app } from 'electron'
import type {
  FusionMode,
  PhrasingMode,
  PipelineResult,
  ProgressUpdate,
  VideoValidation
} from '@shared/types'

/**
 * Starting the Python analysis program and listening to what it says back.
 *
 * The analysis is written in Python because that is where MediaPipe lives, while the app
 * around it is JavaScript. Rather than trying to make one call into the other, the app
 * launches Python as a separate program and the two talk by passing text.
 *
 * Python prints one JSON object per line as it works, and each line is one of three things:
 *
 *   {"type":"progress","stage":"detection","done":12,"total":120}
 *   {"type":"result", ...}
 *   {"type":"error","message":"..."}
 *
 * Running it separately has a useful side effect. Analysis takes minutes, and if it ran
 * inside the app the whole window would sit frozen throughout. As its own program it can
 * take as long as it needs while the interface stays responsive and shows progress.
 */

/** Directory holding the Python pipeline (dev vs packaged). */
function pipelineDir(): string {
  return app.isPackaged
    ? join(process.resourcesPath, 'pipeline')
    : join(app.getAppPath(), 'pipeline')
}

/**
 * Find the Python to run.
 *
 * Prefers the one in the project's own virtual environment, because that is where MediaPipe
 * is installed at a version known to work. Falls back to whatever Python is on the system,
 * which is enough for the self-test since that needs no extra libraries.
 */
function pythonExecutable(): string {
  const venv = join(pipelineDir(), '.venv', 'Scripts', 'python.exe')
  return existsSync(venv) ? venv : 'python'
}

/**
 * How long to wait for the upload check before giving up on it.
 *
 * It normally finishes in two or three seconds. The limit exists so that a Python process
 * which somehow hangs cannot leave the user staring at a screen that never comes back. If
 * it is ever hit, the file is not refused: a check that failed to run says nothing at all
 * about the video, and refusing on those grounds would block a perfectly good recording.
 */
const VALIDATE_TIMEOUT_MS = 60_000

/**
 * Ask Python whether a chosen video can be analysed.
 *
 * Only Python can answer this. It is the side with the video library and the detector, so
 * it is the only side that can open the file, read how long it is and see whether anybody
 * is in it. Doing the same work here would mean shipping a second copy of a video decoder
 * inside the app for no benefit.
 *
 * This never rejects because a video was refused. A refusal is an ordinary answer and comes
 * back as `ok: false` with a reason to show the user. The promise only rejects if the check
 * could not be carried out at all, and the caller treats that as "unknown", not as "bad".
 */
export function validateVideoFile(
  videoPath: string,
  minDurationS: number
): Promise<VideoValidation> {
  return new Promise((resolve, reject) => {
    const args = [
      'run.py',
      '--validate',
      '--video',
      videoPath,
      '--min-duration',
      String(minDurationS)
    ]
    const child = spawn(pythonExecutable(), args, { cwd: pipelineDir() })

    let validation: VideoValidation | null = null
    let errorMsg: string | null = null
    const stderr: string[] = []

    const timer = setTimeout(() => {
      errorMsg = 'The video check took too long and was stopped.'
      child.kill()
    }, VALIDATE_TIMEOUT_MS)

    const rl = createInterface({ input: child.stdout })
    rl.on('line', (line) => {
      const trimmed = line.trim()
      if (!trimmed) return
      let msg: Record<string, unknown>
      try {
        msg = JSON.parse(trimmed)
      } catch {
        return // MediaPipe writes its own notices to the console; they are not our messages
      }
      if (msg.type === 'result') validation = msg as unknown as VideoValidation
      if (msg.type === 'error') errorMsg = String(msg.message ?? 'Unknown validation error')
    })

    child.stderr.on('data', (d) => stderr.push(d.toString()))

    child.on('error', (err) => {
      clearTimeout(timer)
      reject(new Error(`Could not start the video check: ${err.message}`))
    })

    child.on('close', (code) => {
      clearTimeout(timer)
      if (validation) resolve(validation)
      else if (errorMsg) reject(new Error(errorMsg))
      else reject(new Error(`The video check failed (exit ${code}): ${stderr.join('')}`))
    })
  })
}

/**
 * Turn a failure from the Python side into something a person can act on.
 *
 * Most of what comes back is already fit to read, because the pipeline reports its own
 * problems in plain words. One case is not: when the analysis software itself is not present
 * on the machine, Python fails with a message like "No module named 'cv2'", which is precise,
 * accurate and completely meaningless to somebody who just wanted feedback on their practice
 * interview.
 *
 * That case is not hypothetical. The installer carries the analysis code but not the Python
 * that runs it, because that would add several hundred megabytes and needs a matching
 * interpreter underneath, so anybody who installs this without already having that set up meets
 * exactly this. They are pointed at the one step that fixes it.
 */
export function explainPythonFailure(raw: string): string {
  const missingModule = /No module named ['"]?([\w.]+)/.exec(raw)
  const couldNotStart = /Failed to start Python|ENOENT|is not recognized/i.test(raw)

  if (missingModule || couldNotStart) {
    return (
      'This copy of BodyTalk cannot analyse videos yet, because the analysis software it ' +
      'needs is not set up on this computer. Running setup.ps1, in the pipeline folder where ' +
      'BodyTalk is installed, puts it in place. Everything else, including opening and ' +
      'reading sessions analysed elsewhere, works without it.' +
      (missingModule ? ` (The missing part is "${missingModule[1]}".)` : '')
    )
  }
  return raw
}

export interface RunPipelineOptions {
  sessionId: number
  fusionMode: FusionMode
  videoPath?: string
  analysisFps?: number
  /**
   * The folder this session owns, which is where the pipeline puts the files it produces.
   *
   * This has to be passed. Without it the pipeline has no idea where the app keeps its
   * files, so it falls back to writing the landmark data into a folder beside the video it
   * was given. That is somebody's own folder, wherever they happened to keep the recording,
   * and the file left there is a frame-by-frame record of where their body was throughout.
   * It also survives deleting the session, because deletion removes the session folder and
   * nothing else, so a user could delete a practice run and leave the detailed version of it
   * behind without ever being told.
   */
  outDir?: string
  /** How the advice should be worded. Defaults to the rules' own sentences. */
  phrasing?: PhrasingMode
  /** Run the dependency-free self-test (no MediaPipe needed). */
  selfTest?: boolean
  onProgress: (update: ProgressUpdate) => void
}

const running = new Map<number, ChildProcessWithoutNullStreams>()

export function runPipeline(opts: RunPipelineOptions): Promise<PipelineResult> {
  return new Promise((resolve, reject) => {
    const args = ['run.py', '--session-id', String(opts.sessionId), '--fusion', opts.fusionMode]
    if (opts.selfTest) {
      args.push('--selftest')
    } else {
      if (opts.videoPath) args.push('--video', opts.videoPath)
      if (opts.analysisFps) args.push('--fps', String(opts.analysisFps))
      if (opts.outDir) args.push('--out', opts.outDir)
      if (opts.phrasing) args.push('--phrasing', opts.phrasing)
    }

    const child = spawn(pythonExecutable(), args, { cwd: pipelineDir() })
    running.set(opts.sessionId, child)

    let result: PipelineResult | null = null
    let errorMsg: string | null = null
    const stderr: string[] = []

    const rl = createInterface({ input: child.stdout })
    rl.on('line', (line) => {
      const trimmed = line.trim()
      if (!trimmed) return
      let msg: Record<string, unknown>
      try {
        msg = JSON.parse(trimmed)
      } catch {
        return // not one of our messages, so ignore it rather than crashing
      }
      switch (msg.type) {
        case 'progress':
          opts.onProgress({
            sessionId: opts.sessionId,
            stage: String(msg.stage ?? ''),
            done: Number(msg.done ?? 0),
            total: Number(msg.total ?? 0)
          })
          break
        case 'result': {
          // "type" is how the line announced itself on the way over, not part of the
          // result. Dropping it here keeps that detail of how the two programs talk from
          // spreading into everything downstream that handles a result.
          const { type: _transport, ...payload } = msg
          result = payload as unknown as PipelineResult
          break
        }
        case 'error':
          errorMsg = String(msg.message ?? 'Unknown pipeline error')
          break
      }
    })

    child.stderr.on('data', (d) => stderr.push(d.toString()))

    child.on('error', (err) => {
      running.delete(opts.sessionId)
      reject(new Error(`Failed to start Python pipeline: ${err.message}`))
    })

    child.on('close', (code, signal) => {
      running.delete(opts.sessionId)
      if (signal === 'SIGTERM') {
        reject(new Error('cancelled'))
      } else if (errorMsg) {
        reject(new Error(explainPythonFailure(errorMsg)))
      } else if (code !== 0) {
        reject(
          new Error(explainPythonFailure(`Pipeline exited with code ${code}: ${stderr.join('')}`))
        )
      } else if (!result) {
        reject(new Error('Pipeline produced no result.'))
      } else {
        resolve(result)
      }
    })
  })
}

/** Stop a run that is still going, when the user presses cancel. */
export function cancelPipeline(sessionId: number): void {
  running.get(sessionId)?.kill('SIGTERM')
}
