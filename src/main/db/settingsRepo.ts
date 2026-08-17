import { dbAll, dbRun, persist } from './database'
import type { AppSettings } from '@shared/types'

// Still to confirm once there is real timing data: how many frames a second to analyse by
// default, and how short a video is too short to say anything useful about.
const DEFAULTS: AppSettings = { analysisFps: 6, reportSavePath: null, minDurationS: 60 }

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
