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
  -- The score for each channel, exactly as the analysis calculated it. Stored rather than
  -- worked out again from window_scores, because a window where a channel could not be
  -- measured has no score and has to be left out of the average instead of counted as zero.
  -- Getting that wrong makes a channel that was out of shot look like a channel that did
  -- badly, and that mistake was made once already.
  face_score       REAL,
  pose_score       REAL,
  hands_score      REAL,
  -- The sentence shown at the top of the results, written by the analysis from what it
  -- actually found. Kept here rather than rebuilt on screen for the same reason as the
  -- scores above: it should say the same thing everywhere it appears.
  overall_summary  TEXT,
  -- Whether that sentence was assembled from fixed wording or reworded by a language model.
  -- Always 'template' at the moment. It exists so that any piece of text in a finished
  -- report can be traced back to how it was produced, which matters because the model is
  -- only ever allowed to reword findings, never to make them.
  summary_phrasing TEXT,
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
  suggestion  TEXT,
  phrasing    TEXT
);

-- What the user is advised to do next, worked out from the events above.
--
-- Its own table rather than columns on sessions, because there is a list of these per
-- session and the number varies, which is the same shape as events and stored the same way.
--
-- Nothing here is a new finding. Each row is built from events that were actually detected,
-- and basis_event_types records which ones, so any piece of advice can be traced back to the
-- observation behind it. That trail is what keeps the advice tied to what was seen rather
-- than to an opinion about the person.
CREATE TABLE IF NOT EXISTS recommendations (
  id                INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id        INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  rank              INTEGER NOT NULL,
  channel           TEXT NOT NULL,
  kind              TEXT NOT NULL,
  title             TEXT NOT NULL,
  body              TEXT NOT NULL,
  basis_event_types TEXT,
  phrasing          TEXT
);

CREATE TABLE IF NOT EXISTS settings (
  key   TEXT PRIMARY KEY,
  value TEXT
);

CREATE INDEX IF NOT EXISTS idx_window_scores_session ON window_scores(session_id);
CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_id);
CREATE INDEX IF NOT EXISTS idx_recommendations_session ON recommendations(session_id);
