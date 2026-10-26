import { describe, it, expect, beforeEach, afterAll, vi } from 'vitest'
import { mkdtempSync, rmSync, existsSync } from 'fs'
import { tmpdir } from 'os'
import { join, resolve } from 'path'

/**
 * The database refuses values that would make a stored session wrong.
 *
 * The rules live in the table definitions: the fusion method has to be one of the two the
 * comparison is about, a score has to belong to a face, posture, hands or combined row, a score
 * has to belong to a session that exists, and a session has to say which video it came from.
 * These run the real data layer against a real database file, like the deletion tests, and
 * check each rule is actually enforced rather than only written down.
 *
 * The last test repeats one rule after a save. Saving reopens the database underneath, and that
 * once switched the rule about scores belonging to a session off without anyone noticing.
 */
const appData = mkdtempSync(join(tmpdir(), 'bodytalk-rules-'))

vi.mock('electron', () => ({
  app: {
    getPath: () => appData,
    getAppPath: () => resolve(__dirname, '..')
  }
}))

import { initDatabase, closeDatabase, dbRun, dbGet, persist } from '../src/main/db/database'
import { ensureStorageLayout } from '../src/main/fs/storage'

const addSession = (id: number, fusion = 'adaptive'): void =>
  dbRun(
    `INSERT INTO sessions (id, created_at, video_filename, fusion_mode, status)
     VALUES (?, 'now', 'practice.mp4', ?, 'complete')`,
    [id, fusion]
  )

const addScore = (sessionId: number, channel = 'face'): void =>
  dbRun(
    `INSERT INTO window_scores (session_id, t_start_s, t_end_s, channel, raw_score)
     VALUES (?, 0, 1, ?, 80)`,
    [sessionId, channel]
  )

const sessions = (): number => dbGet<{ n: number }>('SELECT COUNT(*) AS n FROM sessions')?.n ?? -1

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

describe('values the database refuses', () => {
  it('accepts a correct session and score, so the refusals below mean something', () => {
    addSession(1)
    addScore(1)
    expect(sessions()).toBe(1)
  })

  it('refuses a fusion method other than adaptive or fixed', () => {
    expect(() => addSession(1, 'average')).toThrow(/CHECK/)
    expect(sessions()).toBe(0)
  })

  it('refuses a score for a part of the body it does not measure', () => {
    addSession(1)
    expect(() => addScore(1, 'eyes')).toThrow(/CHECK/)
  })

  it('refuses a score for a session that does not exist', () => {
    expect(() => addScore(99)).toThrow(/FOREIGN KEY/)
  })

  it('refuses a session that does not say which video it came from', () => {
    expect(() =>
      dbRun(
        `INSERT INTO sessions (id, created_at, fusion_mode, status)
         VALUES (1, 'now', 'adaptive', 'complete')`
      )
    ).toThrow(/NOT NULL/)
  })

  it('still refuses a score for a missing session after the database has been saved', () => {
    persist()
    expect(() => addScore(99)).toThrow(/FOREIGN KEY/)
  })
})
