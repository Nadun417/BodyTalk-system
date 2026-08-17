-- The database tables BodyTalk stores everything in.
--
-- Every statement checks whether the table already exists first, so this file can safely
-- be run every single time the app starts. That is simpler than tracking which version of
-- the database a user happens to have.
--
-- One thing here is more important than it looks. The window_scores table keeps the
-- visibility and the weight for every channel of every second of video, not just the score.
-- Those two columns are the whole record of the adaptive weighting actually doing
-- something, and they are what both the weight chart and the comparison between the two
-- fusion modes are built from. Dropping them to save space would leave no evidence behind.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS sessions (
  id               INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at       TEXT NOT NULL,
  video_filename   TEXT NOT NULL,
  video_duration_s REAL,
  analysis_fps     REAL,
  fusion_mode      TEXT NOT NULL CHECK (fusion_mode IN ('adaptive', 'fixed')),
  overall_score    REAL,
  status           TEXT NOT NULL DEFAULT 'pending'
);

CREATE TABLE IF NOT EXISTS window_scores (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id  INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  t_start_s   REAL NOT NULL,
  t_end_s     REAL NOT NULL,
  channel     TEXT NOT NULL CHECK (channel IN ('face', 'pose', 'hands', 'fused')),
  raw_score   REAL,
  visibility  REAL,
  weight      REAL
);

CREATE TABLE IF NOT EXISTS events (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id  INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  t_start_s   REAL NOT NULL,
  t_end_s     REAL NOT NULL,
  channel     TEXT NOT NULL,
  type        TEXT NOT NULL,
  severity    TEXT NOT NULL,
  message     TEXT NOT NULL,
  suggestion  TEXT
);

CREATE TABLE IF NOT EXISTS settings (
  key   TEXT PRIMARY KEY,
  value TEXT
);

CREATE INDEX IF NOT EXISTS idx_window_scores_session ON window_scores(session_id);
CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_id);
