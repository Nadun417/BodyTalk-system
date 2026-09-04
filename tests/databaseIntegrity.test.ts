import { describe, it, expect, beforeEach, afterAll, vi } from 'vitest'
import { mkdtempSync, rmSync, existsSync } from 'fs'
import { tmpdir } from 'os'
import { join, resolve } from 'path'

/**
 * Deleting a session has to take everything belonging to it.
 *
 * This one runs the real data layer against a real database file in a temporary folder,
 * rather than standing anything in for it, because the fault it guards against lived
 * entirely in the parts a stand-in would have replaced.
 *
 * What happened: SQLite starts with foreign keys switched off, and the setting belongs to
 * the open connection rather than to the database file. The app turned it on once at
 * startup, which looks correct and reads correctly. But saving the database asks sql.js for
 * the bytes, and doing that closes the database and opens it again underneath, which starts
 * a fresh connection with the setting back off. The very first save happened during startup,
 * so in practice the rule was never in force at all. Deleting a session removed the session
 * row and left every score and comment it held sitting in the database, with the app showing
 * the session as gone.
 *
 * For this project that is a privacy fault rather than an untidiness: those rows are a
 * second-by-second record of where a person's body was, from a practice run they chose to
 * delete.
 */
const appData = mkdtempSync(join(tmpdir(), 'bodytalk-test-'))

vi.mock('electron', () => ({
  app: {
    getPath: () => appData,
    // The database engine is a WebAssembly file loaded from node_modules, so this has to be
    // the real project folder.
    getAppPath: () => resolve(__dirname, '..')
  }
}))

import { initDatabase, closeDatabase, dbRun, dbAll, dbGet, persist } from '../src/main/db/database'
import { ensureStorageLayout } from '../src/main/fs/storage'

const countIn = (table: string, sessionId: number): number =>
  dbGet<{ n: number }>(`SELECT COUNT(*) AS n FROM ${table} WHERE session_id = ?`, [sessionId])?.n ??
  -1

const addSessionWithRows = (id: number): void => {
  dbRun(
    `INSERT INTO sessions (id, created_at, video_filename, fusion_mode, status)
     VALUES (?, 'now', 'practice.mp4', 'adaptive', 'complete')`,
    [id]
  )
  dbRun(
    `INSERT INTO window_scores (session_id, t_start_s, t_end_s, channel, raw_score)
     VALUES (?, 0, 1, 'face', 80)`,
    [id]
  )
  dbRun(
    `INSERT INTO events (session_id, t_start_s, t_end_s, channel, type, severity, message)
     VALUES (?, 0, 1, 'face', 'head_movement', 'low', 'Frequent head movement.')`,
    [id]
  )
  dbRun(
    `INSERT INTO recommendations (session_id, rank, channel, kind, title, body)
     VALUES (?, 1, 'face', 'improve', 'Work on eye contact', 'Some advice.')`,
    [id]
  )
}

beforeEach(async () => {
  closeDatabase()
  const file = join(appData, 'BodyTalk', 'bodytalk.db')
  if (existsSync(file)) rmSync(file)
  ensureStorageLayout()
  await initDatabase()
})

afterAll(() => {
  closeDatabase()
  rmSync(appData, { recursive: true, force: true })
})

describe('deleting a session', () => {
  it('takes its scores, comments and advice with it', () => {
    addSessionWithRows(1)
    expect(countIn('window_scores', 1)).toBe(1)

    dbRun(`DELETE FROM sessions WHERE id = ?`, [1])

    expect(countIn('window_scores', 1)).toBe(0)
    expect(countIn('events', 1)).toBe(0)
    expect(countIn('recommendations', 1)).toBe(0)
  })

  /**
   * The specific trap. Saving reopens the database underneath and drops the setting that
   * makes the rule work, so a delete that happens after any save is the one that matters.
   * Before the fix this test failed while the one above passed.
   */
  it('still takes them when the database has been saved first', () => {
    addSessionWithRows(2)
    persist()

    dbRun(`DELETE FROM sessions WHERE id = ?`, [2])

    expect(countIn('window_scores', 2)).toBe(0)
    expect(countIn('events', 2)).toBe(0)
    expect(countIn('recommendations', 2)).toBe(0)
  })

  it('leaves other sessions alone', () => {
    addSessionWithRows(3)
    addSessionWithRows(4)
    persist()

    dbRun(`DELETE FROM sessions WHERE id = ?`, [3])

    expect(countIn('window_scores', 4)).toBe(1)
    expect(dbAll(`SELECT id FROM sessions`)).toHaveLength(1)
  })
})

describe('starting up', () => {
  it('clears out rows left behind by sessions deleted before this was fixed', async () => {
    // Rows with no session, exactly as the old behaviour left them. The rule has to be
    // switched off to create them at all, which is its own demonstration that it works: with
    // it on, the database refuses to accept a row belonging to a session that is not there.
    dbRun(`PRAGMA foreign_keys = OFF`)
    dbRun(
      `INSERT INTO window_scores (session_id, t_start_s, t_end_s, channel, raw_score)
       VALUES (99, 0, 1, 'face', 80)`
    )
    dbRun(
      `INSERT INTO events (session_id, t_start_s, t_end_s, channel, type, severity, message)
       VALUES (99, 0, 1, 'face', 'head_movement', 'low', 'Frequent head movement.')`
    )
    persist()
    expect(countIn('window_scores', 99)).toBe(1)

    closeDatabase()
    await initDatabase()

    expect(countIn('window_scores', 99)).toBe(0)
    expect(countIn('events', 99)).toBe(0)
  })
})
