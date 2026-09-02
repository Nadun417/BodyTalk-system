import { writeFileSync } from 'fs'
import {
  createSession as repoCreate,
  setStatus,
  saveResult,
  deleteSession as repoDelete,
  type CreateSessionInput
} from '../db/sessionRepo'
import { ensureSessionDir, removeSessionDir, resultsPath } from '../fs/storage'
import { runPipeline, cancelPipeline, validateVideoFile } from '../pipeline/pythonBridge'
import type { FusionMode, PipelineResult, ProgressUpdate, VideoValidation } from '@shared/types'

/**
 * Check whether an uploaded video is worth analysing, before spending minutes on it.
 *
 * The checking is done by the Python side, which is the only part of the app that can open
 * a video at all. It looks at whether the file decodes, whether it is long enough for there
 * to be anything worth saying about it, and whether anybody is actually in it. It takes a
 * couple of seconds against several minutes for a full analysis, which is the whole reason
 * it happens first.
 *
 * If the check cannot be run at all, the video is allowed through. That looks like the wrong
 * way round for a validation step, but refusing a file because a check failed would mean
 * blocking a recording that is probably fine on the strength of a problem elsewhere. The
 * analysis itself will fail clearly enough if the file really is unusable, and this way the
 * app is never made unusable by its own safeguard.
 */
export async function validateVideo(
  videoPath: string,
  minDurationS: number
): Promise<VideoValidation> {
  try {
    return await validateVideoFile(videoPath, minDurationS)
  } catch (err) {
    return couldNotCheck((err as Error).message)
  }
}

/**
 * What to report when the check could not be carried out at all.
 *
 * Kept as its own function because it is a decision rather than an error path, and it is the
 * decision most likely to be second-guessed by somebody reading this later. A check that
 * failed to run has told us nothing whatsoever about the video, and "nothing" is not
 * evidence against it. Refusing on those grounds would mean that a Python installation
 * problem presents itself to the user as every single one of their recordings being
 * rejected, with nothing on screen to suggest where the real fault lies.
 *
 * So the video goes through, and the user is told plainly that it was not checked.
 */
export function couldNotCheck(message: string): VideoValidation {
  return {
    ok: true,
    code: 'check_failed',
    warnings: [
      'This video could not be checked before analysing, so any problem with it will ' +
        `only appear once the analysis runs. (${message})`
    ]
  }
}

export function createSession(input: CreateSessionInput): number {
  const id = repoCreate(input)
  ensureSessionDir(id)
  // Still to add: copy the user's video into the session folder, so that reopening an old
  // session still works after they have moved or deleted the original file.
  return id
}

export interface AnalyseOptions {
  sessionId: number
  fusionMode: FusionMode
  videoPath?: string
  analysisFps?: number
  selfTest?: boolean
  onProgress: (update: ProgressUpdate) => void
}

/**
 * Run the analysis and save what comes back.
 *
 * The results are written twice on purpose: once to the database, which is what the
 * dashboard reads, and once as a plain results.json file in the session folder. The second
 * copy costs almost nothing and means a run is never lost to a database problem. It is also
 * far easier to read by hand when checking whether the numbers look sensible.
 *
 * If anything fails, the session is marked accordingly rather than left sitting on
 * "processing" forever, which is what it would otherwise look like to the user.
 */
export async function analyse(opts: AnalyseOptions): Promise<PipelineResult> {
  setStatus(opts.sessionId, 'processing')
  try {
    const result = await runPipeline({
      sessionId: opts.sessionId,
      fusionMode: opts.fusionMode,
      videoPath: opts.videoPath,
      analysisFps: opts.analysisFps,
      selfTest: opts.selfTest,
      onProgress: opts.onProgress
    })
    writeFileSync(resultsPath(opts.sessionId), JSON.stringify(result, null, 2), 'utf-8')
    saveResult(opts.sessionId, result)
    return result
  } catch (err) {
    setStatus(opts.sessionId, (err as Error).message === 'cancelled' ? 'cancelled' : 'error')
    throw err
  }
}

export function cancelAnalysis(sessionId: number): void {
  cancelPipeline(sessionId)
}

/**
 * Delete a session completely: its database rows and its folder of files.
 *
 * Both halves matter. Removing only the database row would leave the copied video sitting
 * on the machine after the user believed they had deleted it.
 */
export function deleteSession(id: number): void {
  repoDelete(id)
  removeSessionDir(id)
}
