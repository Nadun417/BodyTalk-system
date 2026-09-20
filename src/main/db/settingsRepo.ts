import { dbAll, dbRun, persist } from './database'
import type { AppSettings } from '@shared/types'

// The shortest video accepted by default. This has to match the pipeline's own default, because
// the upload screen checks a file by asking the pipeline, and a mismatch would mean the app
// promised to accept something the check then refused.
//
// It moved from sixty seconds to fifty-five on 20 September 2026, after the first recordings
// supplied by somebody other than the author all landed between 57 and 60 seconds and were
// refused over margins as small as three tenths of a second.
//
// Still to confirm once there is real timing data: how many frames a second to analyse by default.
const DEFAULTS: AppSettings = { analysisFps: 6, reportSavePath: null, minDurationS: 55 }

export function getSettings(): AppSettings {
  const rows = dbAll<{ key: string; value: string }>(`SELECT key, value FROM settings`)
  const map = new Map(rows.map((r) => [r.key, r.value]))
  return {
    analysisFps: map.has('analysisFps') ? Number(map.get('analysisFps')) : DEFAULTS.analysisFps,
    reportSavePath: map.get('reportSavePath') || DEFAULTS.reportSavePath,
    minDurationS: map.has('minDurationS') ? Number(map.get('minDurationS')) : DEFAULTS.minDurationS
  }
}

export function setSettings(patch: Partial<AppSettings>): AppSettings {
  for (const [k, v] of Object.entries(patch)) {
    if (v === undefined) continue
    dbRun(
      `INSERT INTO settings (key, value) VALUES (?, ?)
       ON CONFLICT(key) DO UPDATE SET value = excluded.value`,
      [k, v === null ? '' : String(v)]
    )
  }
  persist()
  return getSettings()
}
