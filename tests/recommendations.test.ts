import { describe, it, expect, vi, beforeEach } from 'vitest'
import type { PipelineResult } from '@shared/types'

/**
 * The summary sentence and the advice, on their way into and out of the database.
 *
 * The analysis has always produced both. Nothing on the application side read either of
 * them, so a user saw their scores and the list of moments but never the sentence pulling it
 * together or the advice drawn from it, and the export screen promised recommendations that
 * nothing was keeping. These tests cover the storing and reading that closes that.
 *
 * The part worth protecting is `basisEventTypes`. It records which detected events each
 * piece of advice was built from, and it is what makes the advice traceable back to
 * something actually seen in the video rather than to an opinion about the person. It is
 * stored as one joined string because it is a short list only ever read back whole.
 */
const dbRun = vi.fn()
const dbAll = vi.fn(() => [] as unknown[])
const dbGet = vi.fn()
vi.mock('../src/main/db/database', () => ({
  dbRun: (...args: unknown[]) => dbRun(...args),
  dbAll: (...args: unknown[]) => dbAll(...args),
  dbGet: (...args: unknown[]) => dbGet(...args),
  lastInsertId: vi.fn(() => 1),
  persist: vi.fn(),
  transaction: (fn: () => void) => fn()
}))

import { saveResult, getRecommendations, getSession } from '../src/main/db/sessionRepo'

const statements = (fragment: string): { sql: string; params: unknown[] }[] =>
  dbRun.mock.calls
    .filter((c) => String(c[0]).includes(fragment))
    .map((c) => ({ sql: String(c[0]), params: c[1] as unknown[] }))

const result = (over: Partial<PipelineResult> = {}): PipelineResult => ({
  fusionMode: 'adaptive',
  overallScore: 78.5,
  windows: [],
  events: [],
  ...over
})

describe('saveResult', () => {
  beforeEach(() => vi.clearAllMocks())

  it('stores each piece of advice, in the order the analysis ranked it', () => {
    saveResult(9, {
      ...result(),
      recommendations: [
        {
          rank: 1,
          channel: 'face',
          kind: 'improve',
          title: 'Work on your face and eye contact',
          body: 'Your expression stayed quite still.',
          basisEventTypes: ['flat_expression']
        },
        {
          rank: 2,
          channel: 'pose',
          kind: 'maintain',
          title: 'Keep doing what you did with your posture',
          body: 'This was your strongest channel.',
          basisEventTypes: []
        }
      ]
    })
    const inserts = statements('INSERT INTO recommendations')
    expect(inserts).toHaveLength(2)
    expect(inserts[0].params).toContain('Work on your face and eye contact')
    expect(inserts[0].params).toContain('flat_expression')
    expect(inserts[1].params).toContain(2)
    // Advice based on no particular event stores nothing, not an empty string, so the
    // column has one way of saying "none" rather than two.
    expect(inserts[1].params).toContain(null)
    expect(inserts[1].params).not.toContain('')
  })

  /**
   * Re-analysing a video reuses the session, so anything already stored for it has to go
   * first. Without this the advice from the previous run stays behind and the screen shows
   * both sets at once, which reads as the app contradicting itself.
   */
  it('clears the previous advice before storing the new advice', () => {
    saveResult(9, { ...result(), recommendations: [] })
    expect(statements('DELETE FROM recommendations')).toHaveLength(1)
  })

  it('stores the summary sentence the analysis wrote', () => {
    saveResult(9, { ...result(), overallSummary: 'Your strongest channel was posture.' })
    const [update] = statements('UPDATE sessions')
    expect(update.params).toContain('Your strongest channel was posture.')
  })

  /** The self-test produces neither, which is an ordinary case rather than a fault. */
  it('copes with a run that produced no advice and no summary', () => {
    expect(() => saveResult(9, result())).not.toThrow()
    expect(statements('INSERT INTO recommendations')).toHaveLength(0)
  })
})

describe('getRecommendations', () => {
  beforeEach(() => vi.clearAllMocks())

  it('reads the advice back, splitting the events it was based on', () => {
    dbAll.mockReturnValue([
      {
        rank: 1,
        channel: 'face',
        kind: 'improve',
        title: 'Work on your face and eye contact',
        body: 'Your expression stayed quite still.',
        basis_event_types: 'flat_expression,low_gaze',
        phrasing: 'template'
      }
    ])
    expect(getRecommendations(9)[0].basisEventTypes).toEqual(['flat_expression', 'low_gaze'])
  })

  it('reads advice based on no particular event as an empty list, not a list of nothing', () => {
    dbAll.mockReturnValue([
      {
        rank: 2,
        channel: 'pose',
        kind: 'maintain',
        title: 'Keep doing what you did with your posture',
        body: 'This was your strongest channel.',
        basis_event_types: null,
        phrasing: 'template'
      }
    ])
    expect(getRecommendations(9)[0].basisEventTypes).toEqual([])
  })
})

describe('getSession', () => {
  beforeEach(() => vi.clearAllMocks())

  it('reads the summary back, and leaves an older session without one', () => {
    const row = {
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
      overall_summary: 'Your strongest channel was posture.',
      status: 'complete'
    }
    dbGet.mockReturnValue(row)
    expect(getSession(9)?.overallSummary).toBe('Your strongest channel was posture.')

    dbGet.mockReturnValue({ ...row, overall_summary: null })
    expect(getSession(9)?.overallSummary).toBeNull()
  })
})
