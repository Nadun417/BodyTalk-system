import { describe, it, expect, vi, beforeEach } from 'vitest'

/**
 * Where a run is allowed to leave files.
 *
 * This is here because of a real fault rather than as a precaution. The first time a video
 * was analysed from inside the app, the pipeline was started without being told where to
 * work, so it fell back to writing its landmark data into a folder beside the video it had
 * been handed. On that run it put nearly nine megabytes of frame-by-frame body position
 * into the folder the recording happened to be kept in, where nothing would ever clean it
 * up and deleting the session would not touch it.
 *
 * The rule these tests hold in place is that a session's files go in the session's own
 * folder and nowhere else, because that is the only arrangement in which deleting a session
 * genuinely removes it.
 *
 * Everything the service leans on is replaced below. None of it is under test here, and
 * most of it cannot be imported at all without a running Electron app.
 */
vi.mock('../src/main/db/sessionRepo', () => ({
  createSession: vi.fn(() => 1),
  setStatus: vi.fn(),
  saveResult: vi.fn(),
  deleteSession: vi.fn()
}))
vi.mock('../src/main/fs/storage', () => ({
  ensureSessionDir: vi.fn((id: number) => `/app-data/sessions/${id}`),
  removeSessionDir: vi.fn(),
  resultsPath: vi.fn((id: number) => `/app-data/sessions/${id}/results.json`),
  copyVideoIntoSession: vi.fn(async () => ({ copied: true })),
  sourceVideoPath: vi.fn(() => null)
}))
vi.mock('../src/main/pipeline/pythonBridge', () => ({
  runPipeline: vi.fn(),
  cancelPipeline: vi.fn(),
  validateVideoFile: vi.fn()
}))
vi.mock('fs', () => ({ writeFileSync: vi.fn() }))

import { analyse, createSession } from '../src/main/services/sessionService'
import { runPipeline } from '../src/main/pipeline/pythonBridge'
import { ensureSessionDir, copyVideoIntoSession, sourceVideoPath } from '../src/main/fs/storage'
import { saveResult } from '../src/main/db/sessionRepo'

const mockedRun = vi.mocked(runPipeline)
const emptyResult = { fusionMode: 'adaptive' as const, overallScore: 80, windows: [], events: [] }

describe('analyse', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockedRun.mockResolvedValue(emptyResult)
  })

  it('tells the pipeline to write into the folder belonging to that session', async () => {
    await analyse({
      sessionId: 7,
      fusionMode: 'adaptive',
      videoPath: 'C:/somebody/videos/practice.mp4',
      onProgress: () => {}
    })
    expect(mockedRun.mock.calls[0][0].outDir).toBe('/app-data/sessions/7')
  })

  /**
   * The specific mistake being guarded against. If the output folder is ever left out
   * again, the pipeline writes next to whatever video it was given, and this is the check
   * that fails rather than somebody noticing months later.
   */
  it('never leaves the output folder for the pipeline to guess at', async () => {
    await analyse({
      sessionId: 7,
      fusionMode: 'adaptive',
      videoPath: 'C:/somebody/videos/practice.mp4',
      onProgress: () => {}
    })
    const { outDir } = mockedRun.mock.calls[0][0]
    expect(outDir).toBeTruthy()
    expect(outDir).not.toContain('somebody')
  })

  it('makes sure the folder exists before the pipeline is asked to write into it', async () => {
    await analyse({ sessionId: 7, fusionMode: 'adaptive', onProgress: () => {} })
    expect(vi.mocked(ensureSessionDir)).toHaveBeenCalledWith(7)
  })

  it('saves what came back so the dashboard has something to read', async () => {
    await analyse({ sessionId: 7, fusionMode: 'adaptive', onProgress: () => {} })
    expect(vi.mocked(saveResult)).toHaveBeenCalledWith(7, emptyResult)
  })
})

/**
 * A session keeps its own copy of the video.
 *
 * Without one, a session only knows where the video used to be. Someone who tidies their
 * folders a month later opens an old result and it points at nothing. It also makes deleting
 * a session mean what the app tells the user it means, because the recording being removed
 * is the copy the app made rather than theirs.
 */
describe('createSession', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(copyVideoIntoSession).mockResolvedValue({ copied: true })
  })

  it('takes a copy of the video for the session', async () => {
    await createSession({
      videoFilename: 'practice.mp4',
      videoDurationS: 100,
      analysisFps: 6,
      fusionMode: 'adaptive',
      videoPath: 'C:/somebody/videos/practice.mp4'
    })
    expect(vi.mocked(copyVideoIntoSession)).toHaveBeenCalledWith(
      1,
      'C:/somebody/videos/practice.mp4'
    )
  })

  /**
   * A machine short of space should still be able to analyse a recording. Refusing to, over
   * there being no room for a second copy, would be the worse of the two outcomes: all that
   * is really lost is reopening the session after the original file moves.
   */
  it('still makes the session when there was no room to copy the video', async () => {
    vi.mocked(copyVideoIntoSession).mockResolvedValue({ copied: false, reason: 'ENOSPC' })
    const result = await createSession({
      videoFilename: 'practice.mp4',
      videoDurationS: 100,
      analysisFps: 6,
      fusionMode: 'adaptive',
      videoPath: 'C:/somebody/videos/practice.mp4'
    })
    expect(result.id).toBe(1)
    expect(result.videoCopied).toBe(false)
  })
})

describe('which copy of the video gets analysed', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockedRun.mockResolvedValue(emptyResult)
  })

  it("uses the session's own copy, which cannot be moved out from under the run", async () => {
    vi.mocked(sourceVideoPath).mockReturnValue('/app-data/sessions/7/source.mp4')
    await analyse({
      sessionId: 7,
      fusionMode: 'adaptive',
      videoPath: 'C:/somebody/videos/practice.mp4',
      onProgress: () => {}
    })
    expect(mockedRun.mock.calls[0][0].videoPath).toBe('/app-data/sessions/7/source.mp4')
  })

  it('falls back to where the user picked it when there is no copy', async () => {
    vi.mocked(sourceVideoPath).mockReturnValue(null)
    await analyse({
      sessionId: 7,
      fusionMode: 'adaptive',
      videoPath: 'C:/somebody/videos/practice.mp4',
      onProgress: () => {}
    })
    expect(mockedRun.mock.calls[0][0].videoPath).toBe('C:/somebody/videos/practice.mp4')
  })
})
