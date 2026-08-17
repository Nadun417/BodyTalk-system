import { spawn, ChildProcessWithoutNullStreams } from 'child_process'
import { createInterface } from 'readline'
import { join } from 'path'
import { existsSync } from 'fs'
import { app } from 'electron'
import type { FusionMode, PipelineResult, ProgressUpdate } from '@shared/types'

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

export interface RunPipelineOptions {
  sessionId: number
  fusionMode: FusionMode
  videoPath?: string
  analysisFps?: number
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
        case 'result':
          result = msg as unknown as PipelineResult
          break
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
        reject(new Error(errorMsg))
      } else if (code !== 0) {
        reject(new Error(`Pipeline exited with code ${code}: ${stderr.join('')}`))
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
