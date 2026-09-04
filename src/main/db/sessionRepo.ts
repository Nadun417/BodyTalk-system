import { dbRun, dbAll, dbGet, lastInsertId, transaction, persist } from './database'
import type {
  Session,
  WindowScore,
  AnalysisEvent,
  FusionMode,
  SessionStatus,
  PipelineResult,
  Recommendation
} from '@shared/types'

/** Raw `sessions` row (snake_case) → domain `Session`. */
interface SessionRow {
  id: number
  created_at: string
  video_filename: string
  video_duration_s: number | null
  analysis_fps: number | null
  fusion_mode: FusionMode
  overall_score: number | null
  face_score: number | null
  pose_score: number | null
  hands_score: number | null
  overall_summary: string | null
  status: SessionStatus
}

function toSession(r: SessionRow): Session {
  return {
    id: r.id,
    createdAt: r.created_at,
    videoFilename: r.video_filename,
    videoDurationS: r.video_duration_s ?? 0,
    analysisFps: r.analysis_fps ?? 0,
    fusionMode: r.fusion_mode,
    overallScore: r.overall_score,
    // Kept as null when there is nothing stored, rather than defaulted to a number. A
    // session from before these were recorded has no channel scores, and the screen says so
    // instead of showing a figure nobody calculated.
    channelScores: {
      face: r.face_score ?? null,
      pose: r.pose_score ?? null,
      hands: r.hands_score ?? null
    },
    overallSummary: r.overall_summary ?? null,
    status: r.status
  }
}

export interface CreateSessionInput {
  videoFilename: string
  videoDurationS: number
  analysisFps: number
  fusionMode: FusionMode
}

export function createSession(input: CreateSessionInput): number {
  dbRun(
    `INSERT INTO sessions (created_at, video_filename, video_duration_s, analysis_fps, fusion_mode, status)
     VALUES (?, ?, ?, ?, ?, 'pending')`,
    [
      new Date().toISOString(),
      input.videoFilename,
      input.videoDurationS,
      input.analysisFps,
      input.fusionMode
    ]
  )
  const id = lastInsertId()
  persist()
  return id
}

export function listSessions(): Session[] {
  return dbAll<SessionRow>(`SELECT * FROM sessions ORDER BY created_at DESC`).map(toSession)
}

export function getSession(id: number): Session | null {
  const row = dbGet<SessionRow>(`SELECT * FROM sessions WHERE id = ?`, [id])
  return row ? toSession(row) : null
}

export function getWindowScores(sessionId: number): WindowScore[] {
  return dbAll<WindowScore>(
    `SELECT t_start_s AS tStartS, t_end_s AS tEndS, channel, raw_score AS rawScore,
            visibility, weight
     FROM window_scores WHERE session_id = ? ORDER BY t_start_s`,
    [sessionId]
  )
}

export function getEvents(sessionId: number): AnalysisEvent[] {
  return dbAll<AnalysisEvent>(
    `SELECT t_start_s AS tStartS, t_end_s AS tEndS, channel, type, severity, message,
            suggestion, phrasing
     FROM events WHERE session_id = ? ORDER BY t_start_s`,
    [sessionId]
  )
}

/**
 * The advice for a session, best first.
 *
 * `basis_event_types` is stored as one string because it is a short list that is only ever
 * read back whole, never searched. It records which detected events each piece of advice was
 * built from, which is what lets any advice on screen be traced back to something actually
 * seen in the video.
 */
export function getRecommendations(sessionId: number): Recommendation[] {
  const rows = dbAll<{
    rank: number
    channel: Recommendation['channel']
    kind: string
    title: string
    body: string
    basis_event_types: string | null
    phrasing: Recommendation['phrasing']
  }>(
    `SELECT rank, channel, kind, title, body, basis_event_types, phrasing
     FROM recommendations WHERE session_id = ? ORDER BY rank`,
    [sessionId]
  )
  return rows.map((r) => ({
    rank: r.rank,
    channel: r.channel,
    kind: r.kind,
    title: r.title,
    body: r.body,
    basisEventTypes: r.basis_event_types ? r.basis_event_types.split(',') : [],
    phrasing: r.phrasing
  }))
}

export function setStatus(id: number, status: SessionStatus): void {
  dbRun(`UPDATE sessions SET status = ? WHERE id = ?`, [status, id])
  persist()
}

/**
 * Save a finished run: the overall score, every window score and every comment.
 *
 * All of it goes in as a single operation, so a session is either fully saved or not saved
 * at all. A half-written session would be worse than a failed one, because it would still
 * open and simply show the wrong thing.
 */
export function saveResult(sessionId: number, result: PipelineResult): void {
  transaction(() => {
    dbRun(`DELETE FROM window_scores WHERE session_id = ?`, [sessionId])
    dbRun(`DELETE FROM events WHERE session_id = ?`, [sessionId])
    dbRun(`DELETE FROM recommendations WHERE session_id = ?`, [sessionId])
    for (const w of result.windows) {
      dbRun(
        `INSERT INTO window_scores (session_id, t_start_s, t_end_s, channel, raw_score, visibility, weight)
         VALUES (?, ?, ?, ?, ?, ?, ?)`,
        [sessionId, w.tStartS, w.tEndS, w.channel, w.rawScore, w.visibility, w.weight]
      )
    }
    for (const e of result.events) {
      dbRun(
        `INSERT INTO events (session_id, t_start_s, t_end_s, channel, type, severity, message,
                             suggestion, phrasing)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
        [
          sessionId,
          e.tStartS,
          e.tEndS,
          e.channel,
          e.type,
          e.severity,
          e.message,
          e.suggestion,
          e.phrasing ?? null
        ]
      )
    }
    // Advice is stored in the order the analysis ranked it, and its basis is stored with it
    // so a piece of advice can always be traced back to the events behind it.
    for (const r of result.recommendations ?? []) {
      dbRun(
        `INSERT INTO recommendations (session_id, rank, channel, kind, title, body,
                                      basis_event_types, phrasing)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
        [
          sessionId,
          r.rank,
          r.channel,
          r.kind,
          r.title,
          r.body,
          // Advice drawn from no particular event stores nothing, rather than an empty
          // string, so there is only one way of recording "none" in this column.
          r.basisEventTypes?.length ? r.basisEventTypes.join(',') : null,
          r.phrasing ?? null
        ]
      )
    }
    // The channel scores come from the analysis rather than being worked out here. The
    // self-test does not produce them, so they can legitimately be absent, and absent is
    // stored as nothing rather than as zero.
    const channels = result.channelScores
    dbRun(
      `UPDATE sessions
          SET overall_score = ?, face_score = ?, pose_score = ?, hands_score = ?,
              overall_summary = ?, summary_phrasing = ?, status = 'complete'
        WHERE id = ?`,
      [
        result.overallScore,
        channels?.face ?? null,
        channels?.pose ?? null,
        channels?.hands ?? null,
        result.overallSummary ?? null,
        result.summaryPhrasing ?? null,
        sessionId
      ]
    )
  })
}

export function deleteSession(id: number): void {
  // ON DELETE CASCADE removes window_scores, events and recommendations.
  dbRun(`DELETE FROM sessions WHERE id = ?`, [id])
  persist()
}
