import { describe, it, expect, vi } from 'vitest'

/**
 * What a person is told when the analysis cannot run at all.
 *
 * This is not a hypothetical branch. The installer carries the analysis code but not the
 * Python that runs it, so anybody installing this without that already set up meets exactly
 * this path, and what they were shown was `No module named 'cv2'`. Accurate, and useless to
 * somebody who wanted feedback on a practice interview.
 */
vi.mock('electron', () => ({ app: { isPackaged: false, getAppPath: () => '.' } }))

import { mkdtempSync, readFileSync, rmSync } from 'fs'
import { tmpdir } from 'os'
import { join } from 'path'
import {
  explainPythonFailure,
  explainUnexpectedStop,
  saveErrorDetail
} from '../src/main/pipeline/pythonBridge'

describe('explaining why the analysis could not run', () => {
  it('says what is wrong in words, when a piece of the analysis software is missing', () => {
    const said = explainPythonFailure("No module named 'cv2'")
    expect(said).toContain('cannot analyse videos')
    expect(said).toContain('setup.ps1')
    expect(said).not.toMatch(/^No module named/)
  })

  it('names the missing part, so the fault can still be diagnosed', () => {
    expect(explainPythonFailure("No module named 'mediapipe'")).toContain('mediapipe')
  })

  it('says what does still work, rather than only what does not', () => {
    expect(explainPythonFailure("No module named 'cv2'")).toContain('works without it')
  })

  it('covers Python being absent altogether, not just a missing piece of it', () => {
    const said = explainPythonFailure('Failed to start Python pipeline: spawn python ENOENT')
    expect(said).toContain('not set up on this computer')
  })

  /**
   * Everything else the pipeline reports is already written to be read, so it is passed
   * through untouched. Rewriting messages that were fine would lose detail for no gain.
   */
  it('leaves a message that was already plain alone', () => {
    const original = 'That clip is about 20 seconds long, and at least 60 seconds are needed.'
    expect(explainPythonFailure(original)).toBe(original)
  })
})

/**
 * The analysis program closing part-way without saying why. Found in testing by ending it during
 * a run: the screen filled with the body tracking library's own log lines.
 */
describe('explaining an analysis that stopped part-way', () => {
  const printed =
    'Pipeline exited with code 4294967295: INFO: Created TensorFlow Lite XNNPACK delegate for CPU. ' +
    'W0000 00:00:1793010181.808924 6108 inference_feedback_manager.cc:114] Feedback manager requires ' +
    'a model with a single signature inference.'

  it('says what happened and what to do, in plain words', () => {
    const said = explainUnexpectedStop()
    expect(said).toContain('stopped before it finished')
    expect(said).toContain('Trying again')
    expect(said).not.toMatch(/TensorFlow|W0000|exited with code|\.cc:/)
  })

  it('keeps the printed detail beside the session, and says where', () => {
    const folder = mkdtempSync(join(tmpdir(), 'bodytalk-stop-'))
    const saved = saveErrorDetail(folder, printed)
    expect(saved && readFileSync(saved, 'utf8')).toBe(printed)
    expect(explainUnexpectedStop(saved)).toContain('analysis-error.txt')
    rmSync(folder, { recursive: true, force: true })
  })

  it('does not mention a file when there was nowhere to save one', () => {
    expect(saveErrorDetail(undefined, printed)).toBeUndefined()
    expect(explainUnexpectedStop(undefined)).not.toContain('.txt')
  })

  it('still recognises missing software inside what was printed', () => {
    expect(explainPythonFailure("Pipeline exited with code 1: No module named 'cv2'")).toContain(
      'setup.ps1'
    )
  })
})
