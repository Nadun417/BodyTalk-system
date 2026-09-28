import { describe, it, expect, vi, beforeEach } from 'vitest'
import { DEFAULT_SETTINGS, SETTING_RANGES, clampSetting } from '../src/shared/settings'

/**
 * The settings on their way into and out of the database.
 *
 * These two numbers are the only ones a user can change, and both of them decide how the next
 * analysis behaves: one refuses videos, the other decides how many frames a second of analysis
 * is built from. A silly value in either is not a cosmetic problem. Zero frames a second is a
 * run that produces nothing, and a stored minimum of a million seconds refuses every video the
 * user owns with no obvious way back other than editing the database by hand.
 *
 * So the range is enforced where the values are stored, not only where they are typed. The
 * screen is one way in, and it will not be the only one for long: a database written by an
 * older version of the app, or edited by hand, arrives here the same way.
 */
const rows: { key: string; value: string }[] = []
const dbRun = vi.fn((sql: string, params: unknown[]) => {
  const [key, value] = params as [string, string]
  const existing = rows.find((r) => r.key === key)
  if (existing) existing.value = value
  else rows.push({ key, value })
})

vi.mock('../src/main/db/database', () => ({
  dbRun: (...args: unknown[]) => dbRun(args[0] as string, args[1] as unknown[]),
  dbAll: () => rows,
  dbGet: vi.fn(),
  lastInsertId: vi.fn(() => 1),
  persist: vi.fn(),
  transaction: (fn: () => void) => fn()
}))

import { getSettings, setSettings } from '../src/main/db/settingsRepo'

beforeEach(() => {
  rows.length = 0
  dbRun.mockClear()
})

describe('the allowed range', () => {
  it('keeps a number inside it', () => {
    expect(clampSetting('minDurationS', 5)).toBe(SETTING_RANGES.minDurationS.min)
    expect(clampSetting('minDurationS', 9999)).toBe(SETTING_RANGES.minDurationS.max)
    expect(clampSetting('analysisFps', 0)).toBe(SETTING_RANGES.analysisFps.min)
    expect(clampSetting('analysisFps', 60)).toBe(SETTING_RANGES.analysisFps.max)
  })

  it('leaves a sensible number alone', () => {
    expect(clampSetting('minDurationS', 90)).toBe(90)
    expect(clampSetting('analysisFps', 6)).toBe(6)
  })

  /**
   * An empty box on the settings screen, or an empty row in the table, arrives as something
   * that is not a number at all. Falling back to the normal value is the only answer that
   * leaves the app working; zero would be read as a real choice.
   */
  it('falls back to the normal value when the answer is not a number', () => {
    expect(clampSetting('analysisFps', '')).toBe(DEFAULT_SETTINGS.analysisFps)
    expect(clampSetting('minDurationS', 'soon')).toBe(DEFAULT_SETTINGS.minDurationS)
    expect(clampSetting('analysisFps', null)).toBe(DEFAULT_SETTINGS.analysisFps)
  })
})

describe('settings storage', () => {
  it('starts at the normal settings when nothing has been chosen', () => {
    expect(getSettings()).toEqual(DEFAULT_SETTINGS)
  })

  it('keeps what was chosen, and changes nothing else', () => {
    const after = setSettings({ minDurationS: 90 })
    expect(after.minDurationS).toBe(90)
    expect(after.analysisFps).toBe(DEFAULT_SETTINGS.analysisFps)
  })

  it('stores a number outside the range as the nearest one inside it', () => {
    expect(setSettings({ analysisFps: 240 }).analysisFps).toBe(SETTING_RANGES.analysisFps.max)
    expect(rows.find((r) => r.key === 'analysisFps')?.value).toBe(
      String(SETTING_RANGES.analysisFps.max)
    )
  })

  /**
   * Not everything in this table went through the writer above. A row can predate the range,
   * or have been edited by hand, so the value that actually reaches an analysis is bounded on
   * the way out as well.
   */
  it('bounds a value that was already in the table', () => {
    rows.push({ key: 'analysisFps', value: '0' })
    rows.push({ key: 'minDurationS', value: '100000' })
    const settings = getSettings()
    expect(settings.analysisFps).toBe(SETTING_RANGES.analysisFps.min)
    expect(settings.minDurationS).toBe(SETTING_RANGES.minDurationS.max)
  })

  it('remembers where reports were last saved, and lets that be forgotten', () => {
    expect(setSettings({ reportSavePath: 'C:\\Users\\practice' }).reportSavePath).toBe(
      'C:\\Users\\practice'
    )
    expect(setSettings({ reportSavePath: null }).reportSavePath).toBe(null)
  })
})
