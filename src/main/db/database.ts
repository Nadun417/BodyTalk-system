import { join } from 'path'
import { existsSync, readFileSync, writeFileSync } from 'fs'
import { app } from 'electron'
import initSqlJs, { type Database, type SqlValue } from 'sql.js'
import { dbPath } from '../fs/storage'
import schemaSql from './schema.sql?raw'

/**
 * Data layer backed by sql.js, which is SQLite compiled to WebAssembly. Same engine and
 * the same schema.sql as a native binding, but with zero native compilation so it
 * installs/runs anywhere. Queries are synchronous once initialised; writes are
 * flushed to disk via persist(). The repo API is the swap seam: a native binding
 * (e.g. better-sqlite3) can replace this without touching callers.
 */
let db: Database | null = null

export async function initDatabase(): Promise<void> {
  if (db) return
  // Load the WebAssembly file ourselves rather than letting the library find it. Its own
  // lookup works while developing but not once the app is packaged, where the file ends up
  // somewhere else entirely.
  const buf = readFileSync(
    join(app.getAppPath(), 'node_modules', 'sql.js', 'dist', 'sql-wasm.wasm')
  )
  const wasmBinary = buf.buffer.slice(
    buf.byteOffset,
    buf.byteOffset + buf.byteLength
  ) as ArrayBuffer
  const SQL = await initSqlJs({ wasmBinary })
  const file = dbPath()
  db = existsSync(file) ? new SQL.Database(readFileSync(file)) : new SQL.Database()
  db.run('PRAGMA foreign_keys = ON;')
  db.run(schemaSql)
  addMissingColumns()
  persist()
}

/**
 * Bring a database made by an older version of the app up to the current shape.
 *
 * `schema.sql` only creates tables that are not there yet, which keeps it safe to run on
 * every start but means it can do nothing about a table that already exists. Someone who
 * has been using the app since before a column was added keeps their original table, and
 * the first query mentioning the new column fails on their machine and nowhere else. This
 * adds whatever is missing, and is safe to run every time because a column that is already
 * present is left alone.
 *
 * Rows that already existed get nothing for the new column, which is the right answer
 * rather than a shortcoming. A session analysed before per-channel scores were recorded
 * genuinely has none, and filling one in after the fact would be inventing a result.
 */
function addMissingColumns(): void {
  const wanted: Record<string, string[]> = {
    sessions: [
      'face_score REAL',
      'pose_score REAL',
      'hands_score REAL',
      'overall_summary TEXT',
      'summary_phrasing TEXT'
    ],
    events: ['phrasing TEXT']
  }
  for (const [table, columns] of Object.entries(wanted)) {
    const present = new Set(
      dbAll<{ name: string }>(`PRAGMA table_info(${table})`).map((row) => row.name)
    )
    for (const column of columns) {
      const name = column.split(' ')[0]
      if (!present.has(name)) instance().run(`ALTER TABLE ${table} ADD COLUMN ${column}`)
    }
  }
}

function instance(): Database {
  if (!db) throw new Error('Database not initialised — call initDatabase() first.')
  return db
}

/** Flush the in-memory DB to disk (sql.js holds the DB in memory). */
export function persist(): void {
  if (db) writeFileSync(dbPath(), Buffer.from(db.export()))
}

export function closeDatabase(): void {
  if (db) {
    persist()
    db.close()
    db = null
  }
}

// --- thin sync query helpers (better-sqlite3-like ergonomics) ---

export function dbRun(sql: string, params: SqlValue[] = []): void {
  const stmt = instance().prepare(sql)
  stmt.bind(params)
  stmt.step()
  stmt.free()
}

export function dbAll<T>(sql: string, params: SqlValue[] = []): T[] {
  const stmt = instance().prepare(sql)
  stmt.bind(params)
  const rows: T[] = []
  while (stmt.step()) rows.push(stmt.getAsObject() as T)
  stmt.free()
  return rows
}

export function dbGet<T>(sql: string, params: SqlValue[] = []): T | undefined {
  return dbAll<T>(sql, params)[0]
}

export function lastInsertId(): number {
  const row = dbGet<{ id: number }>('SELECT last_insert_rowid() AS id')
  return row ? Number(row.id) : 0
}

/**
 * Run several database changes as one all-or-nothing operation, saving once at the end.
 *
 * If anything fails partway through, none of it is kept. Without this, a run that broke
 * halfway through saving would leave a session with some of its scores in the database and
 * the rest missing, which looks like a completed session until someone opens it.
 */
export function transaction(fn: () => void): void {
  const d = instance()
  d.run('BEGIN')
  try {
    fn()
    d.run('COMMIT')
  } catch (err) {
    d.run('ROLLBACK')
    throw err
  } finally {
    persist()
  }
}
