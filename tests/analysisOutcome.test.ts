import { describe, it, expect, vi, beforeEach } from 'vitest'
import { IpcChannels } from '@shared/ipcChannels'

/**
 * How an analysis reports the way it ended.
 *
 * There are three endings and the interface has to tell them apart: it finished, the user
 * cancelled it, or it failed. The obvious way to do that is to throw on the last two and
 * read the message on the other side, and that is what this used to do. It does not work.
 * A message thrown in the backend is rewritten on its way to the interface, so "cancelled"
 * arrives as "Error invoking remote method 'analysis:start': Error: cancelled" and no
 * comparison against the original wording matches.
 *
 * What the user saw: they pressed Cancel, the analysis did stop, and they were left sitting
 * on the progress screen with the app's internal plumbing quoted underneath it.
 *
 * So the ending comes back as a plain answer, and these tests hold that in place.
 */
const handlers = new Map<string, (...args: unknown[]) => unknown>()

vi.mock('electron', () => ({
  ipcMain: {
    handle: (channel: string, fn: (...a: unknown[]) => unknown) => handlers.set(channel, fn)
  },
  dialog: { showOpenDialog: vi.fn(), showSaveDialog: vi.fn() },
  BrowserWindow: { getFocusedWindow: () => null }
}))

const analyse = vi.fn()
vi.mock('../src/main/services/sessionService', () => ({
  createSession: vi.fn(),
  validateVideo: vi.fn(),
  analyse: (...args: unknown[]) => analyse(...args),
  cancelAnalysis: vi.fn(),
  deleteSession: vi.fn()
}))
vi.mock('../src/main/db/sessionRepo', () => ({
  listSessions: vi.fn(() => []),
  getSession: vi.fn(),
  getWindowScores: vi.fn(() => []),
  getEvents: vi.fn(() => []),
  getRecommendations: vi.fn(() => [])
}))
vi.mock('../src/main/db/settingsRepo', () => ({
  getSettings: vi.fn(() => ({ analysisFps: 6, reportSavePath: null, minDurationS: 60 })),
  setSettings: vi.fn()
}))

import { registerIpcHandlers } from '../src/main/ipc/handlers'

registerIpcHandlers()
const startAnalysis = handlers.get(IpcChannels.startAnalysis)!
const event = { sender: { isDestroyed: () => false, send: vi.fn() } }
const start = (): Promise<{ cancelled?: boolean; error?: string }> =>
  startAnalysis(event, {
    sessionId: 1,
    fusionMode: 'adaptive',
    videoPath: 'practice.mp4'
  }) as Promise<{
    cancelled?: boolean
    error?: string
  }>

describe('starting an analysis', () => {
  beforeEach(() => vi.clearAllMocks())

  it('says nothing in particular when it finished, which means go to the results', async () => {
    analyse.mockResolvedValue({ fusionMode: 'adaptive', overallScore: 80, windows: [], events: [] })
    expect(await start()).toEqual({})
  })

  it('reports a cancellation as a cancellation, not as a failure', async () => {
    analyse.mockRejectedValue(new Error('cancelled'))
    expect(await start()).toEqual({ cancelled: true })
  })

  it('reports a real failure with the reason, so it can be shown to the user', async () => {
    analyse.mockRejectedValue(new Error('Pipeline exited with code 2: no such file'))
    expect(await start()).toEqual({ error: 'Pipeline exited with code 2: no such file' })
  })

  /**
   * The thing that actually broke. Whatever happens, this settles rather than throwing,
   * because a thrown message is rewritten in transit and stops being recognisable.
   */
  it('never throws, whichever way the analysis ended', async () => {
    analyse.mockRejectedValue(new Error('cancelled'))
    await expect(start()).resolves.toBeDefined()
    analyse.mockRejectedValue(new Error('something else entirely'))
    await expect(start()).resolves.toBeDefined()
  })
})
