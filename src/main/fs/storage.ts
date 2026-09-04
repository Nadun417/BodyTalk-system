import { app } from 'electron'
import { join, extname } from 'path'
import { mkdirSync, existsSync, rmSync, readdirSync } from 'fs'
import { copyFile } from 'fs/promises'

/**
 * Where everything gets stored on the user's own machine.
 *
 *   %APPDATA%/BodyTalk/
 *     bodytalk.db
 *     sessions/<session id>/
 *       source.<ext>        the user's video, copied in (their original is never touched)
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

/**
 * The session's own copy of the video, if it has one.
 *
 * Kept as `source` plus whatever ending the original had, so the format is still obvious
 * from the name. The ending is not known in advance, which is why this looks for the file
 * rather than working out its name: a session recorded from a `.mov` and one from an `.mp4`
 * both end up here.
 *
 * Returns nothing when there is no copy. That is a real case rather than an error. Sessions
 * from before the video was copied in have none, and a copy can also fail on a machine that
 * has run out of room, which is not a reason to make the session unusable.
 */
export function sourceVideoPath(sessionId: number): string | null {
  const dir = sessionDir(sessionId)
  if (!existsSync(dir)) return null
  const match = readdirSync(dir).find((name) => name.startsWith('source.'))
  return match ? join(dir, match) : null
}

/**
 * Take the session's own copy of the video.
 *
 * Copied rather than referenced because a session has to still work months later, and by
 * then the original may well have been renamed, moved onto a different drive or deleted. It
 * is copied rather than moved for the obvious reason: the file belongs to the user and it is
 * not this app's to take away.
 *
 * A failure here is reported rather than thrown. The likeliest cause by far is a machine
 * short of space, and refusing to analyse a perfectly good recording because there was no
 * room for a second copy of it would be a poor trade. The analysis can run from the original
 * either way; what is lost is being able to reopen the session after the original moves.
 */
export async function copyVideoIntoSession(
  sessionId: number,
  videoPath: string
): Promise<{ copied: boolean; reason?: string }> {
  try {
    const suffix = extname(videoPath) || '.mp4'
    await copyFile(videoPath, join(ensureSessionDir(sessionId), `source${suffix}`))
    return { copied: true }
  } catch (err) {
    return { copied: false, reason: (err as Error).message }
  }
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
