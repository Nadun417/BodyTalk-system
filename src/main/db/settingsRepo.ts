import { dbAll, dbRun, persist } from './database'
import type { AppSettings } from '@shared/types'
import { DEFAULT_SETTINGS, clampSetting } from '@shared/settings'

// The defaults and the allowed ranges live with the settings screen's own copy, in
// `src/shared/settings.ts`, so that the screen and this file cannot disagree about what a
// setting is allowed to be. The shortest accepted length also has to match the analysis's own
// default, because the upload screen checks a file by asking the analysis, and a mismatch would
// mean the app promised to accept something the check then refused.
//
// Still to confirm once there is real timing data: how many frames a second to analyse by default.
const DEFAULTS: AppSettings = DEFAULT_SETTINGS

/**
 * The settings the next analysis will run with.
 *
 * Stored numbers are put back inside their allowed range on the way out as well as on the way
 * in. Writing through this file is not the only way a row can end up in the table: a database
 * from an older version of the app, or one somebody has edited by hand, can hold anything at
 * all, and the run has to be sane either way.
 */
export function getSettings(): AppSettings {
  const rows = dbAll<{ key: string; value: string }>(`SELECT key, value FROM settings`)
  const map = new Map(rows.map((r) => [r.key, r.value]))
  return {
    analysisFps: map.has('analysisFps')
      ? clampSetting('analysisFps', map.get('analysisFps'))
      : DEFAULTS.analysisFps,
    reportSavePath: map.get('reportSavePath') || DEFAULTS.reportSavePath,
    minDurationS: map.has('minDurationS')
      ? clampSetting('minDurationS', map.get('minDurationS'))
      : DEFAULTS.minDurationS
  }
}

/**
 * Write the settings that were given, leaving the rest alone.
 *
 * The two numbers are put back inside their allowed range before they are stored, rather than
 * being trusted as they arrive. The screen bounds them too, but this is the side that decides
 * what the next analysis actually runs with, and a stored value of zero frames a second would
 * break every run after it with no obvious way back.
 */
export function setSettings(patch: Partial<AppSettings>): AppSettings {
  for (const [key, raw] of Object.entries(patch)) {
    if (raw === undefined) continue
    const k = key as keyof AppSettings
    const v =
      k === 'analysisFps' || k === 'minDurationS' ? clampSetting(k, raw) : (raw as string | null)
    dbRun(
      `INSERT INTO settings (key, value) VALUES (?, ?)
       ON CONFLICT(key) DO UPDATE SET value = excluded.value`,
      [k, v === null ? '' : String(v)]
    )
  }
  persist()
  return getSettings()
}
