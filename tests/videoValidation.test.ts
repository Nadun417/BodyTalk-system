import { describe, it, expect, vi } from 'vitest'

/**
 * What happens on the application side of the upload check.
 *
 * The check itself lives in Python and is tested there. What is tested here is what this
 * side does with the answer, including the one decision it makes entirely on its own: what
 * to report when the check could not be carried out at all.
 *
 * Everything the service touches besides the check is replaced below. None of it is under
 * test, and most of it cannot even be imported without a running Electron app.
 */
vi.mock('../src/main/db/sessionRepo', () => ({
  createSession: vi.fn(() => 1),
  setStatus: vi.fn(),
  saveResult: vi.fn(),
  deleteSession: vi.fn()
}))
vi.mock('../src/main/fs/storage', () => ({
  ensureSessionDir: vi.fn(),
  removeSessionDir: vi.fn(),
  resultsPath: vi.fn(() => 'results.json')
}))
vi.mock('../src/main/pipeline/pythonBridge', () => ({
  runPipeline: vi.fn(),
  cancelPipeline: vi.fn(),
  validateVideoFile: vi.fn()
}))

import { validateVideo, couldNotCheck } from '../src/main/services/sessionService'
import { validateVideoFile } from '../src/main/pipeline/pythonBridge'

const mockedCheck = vi.mocked(validateVideoFile)

describe('validateVideo', () => {
  it('passes on a refusal so the reason can be shown to the user', async () => {
    mockedCheck.mockResolvedValue({
      ok: false,
      code: 'too_short',
      reason: 'That clip is about 20 seconds long, and at least 60 seconds are needed.',
      durationS: 20
    })
    const result = await validateVideo('short.mp4', 60)
    expect(result.ok).toBe(false)
    expect(result.reason).toContain('60 seconds')
  })

  it('passes on an acceptance along with anything worth mentioning', async () => {
    mockedCheck.mockResolvedValue({
      ok: true,
      code: 'ok',
      durationS: 120,
      warnings: ['Only one person is analysed.']
    })
    const result = await validateVideo('good.mp4', 60)
    expect(result.ok).toBe(true)
    expect(result.warnings).toHaveLength(1)
  })

  it('asks with the configured minimum length rather than one of its own', async () => {
    mockedCheck.mockResolvedValue({ ok: true, code: 'ok', durationS: 120 })
    await validateVideo('good.mp4', 45)
    expect(mockedCheck).toHaveBeenCalledWith('good.mp4', 45)
  })
})

describe('couldNotCheck', () => {
  /**
   * The rule worth pinning down, because it looks backwards at first glance: when the check
   * fails, the video is allowed through rather than refused.
   *
   * A check that did not run has said nothing about the video, and nothing is not evidence
   * against it. Refusing here would mean a broken Python setup appears to the user as every
   * one of their recordings being rejected, with no hint of where the real fault lies.
   */
  it('lets the video through rather than refusing it', () => {
    expect(couldNotCheck('ENOENT').ok).toBe(true)
  })

  it('marks itself as a check that did not happen, not as a passing video', () => {
    expect(couldNotCheck('ENOENT').code).toBe('check_failed')
  })

  it('says so plainly instead of staying silent', () => {
    const warnings = couldNotCheck('ENOENT').warnings?.join(' ') ?? ''
    expect(warnings).toContain('could not be checked')
  })

  it('includes what actually went wrong, so a broken setup can be diagnosed', () => {
    expect(couldNotCheck('ENOENT').warnings?.join(' ')).toContain('ENOENT')
  })
})
