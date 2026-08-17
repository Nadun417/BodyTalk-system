import { app } from 'electron'
import { join } from 'path'
import { mkdirSync, existsSync, rmSync } from 'fs'

/**
 * Where everything gets stored on the user's own machine.
 *
 *   %APPDATA%/BodyTalk/
 *     bodytalk.db
 *     sessions/<session id>/
 *       source.<ext>        the user's video, copied in
 *       frames/             cached frames, safe to clear
 *       landmarks.jsonl     the detected landmarks for every sampled frame
 *       results.json        the finished scores and comments
 *       report-<date>.pdf
 *
 * Everything for one session sits in one folder, which is what makes deleting a session
 * genuinely delete it. Scattering a session's files around would mean bits of someone's
 * practice video surviving a deletion they thought had removed it, and given what these
 * recordings contain that is worth avoiding.
 *
 * All file handling lives in the backend. The interface never reads or writes anything
 * itself; it asks for what it needs. That way there is a single place where files are
 * touched, rather than file access spread through the part of the app that renders buttons.
 */
export function appDataRoot(): string {
  return join(app.getPath('appData'), 'BodyTalk')
}

export function dbPath(): string {
  return join(appDataRoot(), 'bodytalk.db')
}

export function sessionsRoot(): string {
  return join(appDataRoot(), 'sessions')
}

export function sessionDir(sessionId: number): string {
  return join(sessionsRoot(), String(sessionId))
}

export function resultsPath(sessionId: number): string {
  return join(sessionDir(sessionId), 'results.json')
}

/** Make sure the top-level folders exist. Runs once when the app starts. */
export function ensureStorageLayout(): void {
  mkdirSync(sessionsRoot(), { recursive: true })
}

/** Create the folder for one session, along with its frame cache. */
export function ensureSessionDir(sessionId: number): string {
  const dir = sessionDir(sessionId)
  mkdirSync(join(dir, 'frames'), { recursive: true })
  return dir
}

/**
 * Remove everything belonging to one session from the disk.
 *
 * This takes the whole folder, which is the point. The copied video, the landmarks and any
 * reports all go together, so the user does not delete a session from the list and leave
 * their recording sitting on the machine.
 */
export function removeSessionDir(sessionId: number): void {
  const dir = sessionDir(sessionId)
  if (existsSync(dir)) rmSync(dir, { recursive: true, force: true })
}
