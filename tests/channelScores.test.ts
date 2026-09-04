import { describe, it, expect, vi, beforeEach } from 'vitest'
import type { PipelineResult } from '@shared/types'

/**
 * The per-channel scores on their way into and out of the database.
 *
 * These are carried through from the analysis rather than worked out again, and that is the
 * whole point of the tests below. The screen used to average the per-window scores itself,
 * which counted a window where the channel could not be measured as though the channel had
 * scored zero. On a real recording that reported 92 for hands where the analysis had
 * calculated 93, and a channel actually out of shot for a longer stretch would have been
 * dragged down much further than that. A channel nobody could see is not a channel that did
 * badly, and telling somebody their gestures were poor when the camera simply missed them is
 * the exact mistake the weighting exists to prevent.
 *
 * So there is one place these numbers are calculated, and everywhere else passes them along.
 */
const dbRun = vi.fn()
const dbGet = vi.fn()
vi.mock('../src/main/db/database', () => ({
  dbRun: (...args: unknown[]) => dbRun(...args),
  dbAll: vi.fn(() => []),
  dbGet: (...args: unknown[]) => dbGet(...args),
  lastInsertId: vi.fn(() => 1),
  persist: vi.fn(),
  transaction: (fn: () => void) => fn()
}))

import { saveResult, getSession } from '../src/main/db/sessionRepo'

/** The UPDATE that finishes a session, picked out of everything saveResult runs. */
const finishingUpdate = (): { sql: string; params: unknown[] } => {
  const call = dbRun.mock.calls.find((c) => String(c[0]).includes('UPDATE sessions'))
  if (!call) throw new Error('no UPDATE sessions statement was run')
  return { sql: String(call[0]), params: call[1] as unknown[] }
}

const resultWith = (channelScores?: PipelineResult['channelScores']): PipelineResult => ({
  fusionMode: 'adaptive',
  overallScore: 78.5,
  channelScores,
  windows: [],
  events: []
})

describe('saveResult', () => {
  beforeEach(() => vi.clearAllMocks())

  it('stores the scores the analysis calculated, unchanged', () => {
    saveResult(9, resultWith({ face: 66.4, pose: 98.3, hands: 71.4 }))
    const { params } = finishingUpdate()
    expect(params).toContain(66.4)
    expect(params).toContain(98.3)
    expect(params).toContain(71.4)
  })

  /**
   * The self-test deliberately returns a minimal result, so absent scores are an ordinary
   * case rather than a fault. Nothing recorded has to stay nothing recorded: a zero here
   * would appear on screen as a channel that scored zero.
   */
  it('stores nothing rather than zero when the run produced no channel scores', () => {
    saveResult(9, resultWith(undefined))
    const { params } = finishingUpdate()
    // Overall score, the three channels, the summary and how it was worded, then the id.
    // Spelled out in full so that adding another column forces a decision about what an
    // absent value means, rather than letting a zero slip in unnoticed.
    expect(params).toEqual([78.5, null, null, null, null, null, 9])
    expect(params).not.toContain(0)
  })
})

describe('getSession', () => {
  beforeEach(() => vi.clearAllMocks())

  it('reads the stored scores back', () => {
    dbGet.mockReturnValue({
      id: 9,
      created_at: 'now',
      video_filename: 'practice.mp4',
      video_duration_s: 101.3,
      analysis_fps: 6,
      fusion_mode: 'adaptive',
      overall_score: 78.5,
      face_score: 66.4,
      pose_score: 98.3,
      hands_score: 71.4,
      status: 'complete'
    })
    expect(getSession(9)?.channelScores).toEqual({ face: 66.4, pose: 98.3, hands: 71.4 })
  })

  /**
   * Sessions analysed before these were recorded genuinely have no channel scores. The
   * screen shows a dash for them, which is only possible if nothing turns the missing value
   * into a number on the way through.
   */
  it('leaves a session recorded before these existed with nothing, not with zeros', () => {
    dbGet.mockReturnValue({
      id: 6,
      created_at: 'then',
      video_filename: 'older.mp4',
      video_duration_s: 139.4,
      analysis_fps: 6,
      fusion_mode: 'adaptive',
      overall_score: 88.1,
      face_score: null,
      pose_score: null,
      hands_score: null,
      status: 'complete'
    })
    expect(getSession(6)?.channelScores).toEqual({ face: null, pose: null, hands: null })
  })
})
