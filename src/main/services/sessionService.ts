import { writeFileSync } from 'fs'
import {
  createSession as repoCreate,
  setStatus,
  saveResult,
  deleteSession as repoDelete,
  type CreateSessionInput
} from '../db/sessionRepo'
import { ensureSessionDir, removeSessionDir, resultsPath } from '../fs/storage'
import { runPipeline, cancelPipeline } from '../pipeline/pythonBridge'
import type { FusionMode, PipelineResult, ProgressUpdate, VideoValidation } from '@shared/types'

/**
 * Check whether an uploaded video is worth analysing, before spending minutes on it.
 *
 * Currently accepts everything. The real checks are written later: that the file actually
 * opens, that it is long enough to show sustained behaviour rather than a moment, and that
 * somebody is visible in the opening seconds. Catching those up front saves the user
 * waiting through a long analysis only to be told at the end that it was never going to work.
 */
export function validateVideo(_videoPath: string, _minDurationS: number): VideoValidation {
  // Still to settle: which video formats to accept, an upper size limit, and whether the
  // length is read using the pipeline itself or a separate tool.
  return { ok: true }
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
