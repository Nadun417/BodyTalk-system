import { dbRun, dbAll, dbGet, lastInsertId, transaction, persist } from './database'
import type {
  Session,
  WindowScore,
  AnalysisEvent,
  FusionMode,
  SessionStatus,
  PipelineResult
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
    `SELECT t_start_s AS tStartS, t_end_s AS tEndS, channel, type, severity, message, suggestion
     FROM events WHERE session_id = ? ORDER BY t_start_s`,
    [sessionId]
  )
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
    for (const w of result.windows) {
      dbRun(
        `INSERT INTO window_scores (session_id, t_start_s, t_end_s, channel, raw_score, visibility, weight)
         VALUES (?, ?, ?, ?, ?, ?, ?)`,
        [sessionId, w.tStartS, w.tEndS, w.channel, w.rawScore, w.visibility, w.weight]
      )
    }
    for (const e of result.events) {
      dbRun(
        `INSERT INTO events (session_id, t_start_s, t_end_s, channel, type, severity, message, suggestion)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
        [sessionId, e.tStartS, e.tEndS, e.channel, e.type, e.severity, e.message, e.suggestion]
      )
    }
    dbRun(`UPDATE sessions SET overall_score = ?, status = 'complete' WHERE id = ?`, [
      result.overallScore,
      sessionId
    ])
  })
}

export function deleteSession(id: number): void {
  // ON DELETE CASCADE removes window_scores + events.
  dbRun(`DELETE FROM sessions WHERE id = ?`, [id])
  persist()
}
