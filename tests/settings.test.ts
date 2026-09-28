import { describe, it, expect, vi, beforeEach } from 'vitest'
import { readFileSync } from 'fs'
import { resolve } from 'path'
import {
  ANALYSIS_FPS_WARNING,
  DEFAULT_SETTINGS,
  SETTING_RANGES,
  SHORT_VIDEO_WARNING,
  clampSetting,
  settingChoices
} from '../src/shared/settings'

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

describe('the lists on the settings screen', () => {
  it('offers every allowed length, in steps, with the recommended one among them', () => {
    const lengths = settingChoices('minDurationS')
    expect(lengths[0]).toBe(SETTING_RANGES.minDurationS.min)
    expect(lengths[lengths.length - 1]).toBe(SETTING_RANGES.minDurationS.max)
    expect(lengths).toContain(DEFAULT_SETTINGS.minDurationS)
    expect(lengths.every((n, i) => i === 0 || n - lengths[i - 1] === 5)).toBe(true)
  })

  it('offers every allowed number of pictures a second', () => {
    expect(settingChoices('analysisFps')).toEqual([5, 6, 7, 8, 9, 10])
  })

  /**
   * A length saved before the lists existed need not be on a step. The list has to show what
   * is actually in use rather than quietly showing its nearest neighbour.
   */
  it('keeps a stored value that is not on a step, in its place in the list', () => {
    const lengths = settingChoices('minDurationS', 57)
    expect(lengths).toContain(57)
    expect(lengths.indexOf(57)).toBe(lengths.indexOf(55) + 1)
    expect(settingChoices('minDurationS', 55).filter((n) => n === 55)).toHaveLength(1)
  })
})

describe('what the warnings say', () => {
  /**
   * The short-video warning quotes two durations from the rules that decide what is reported.
   * If either rule ever changes, the warning would be telling people something untrue, so this
   * reads the rules themselves and checks the numbers still agree.
   */
  it('quotes the same durations the rules actually use', () => {
    const rules = readFileSync(resolve(__dirname, '../pipeline/feedback/rules.py'), 'utf-8')
    const durationOf = (type: string): number => {
      // A rule is written as its duration, then its part of the body, then its name, each on a
      // line of its own, so the number two lines above the name is its duration.
      const found = new RegExp(String.raw`(\d+(?:\.\d+)?),\s*\n\s*"\w+",\s*\n\s*"${type}"`).exec(
        rules
      )
      if (!found) throw new Error(`no rule found for ${type}`)
      return Number(found[1])
    }
    expect(SHORT_VIDEO_WARNING).toContain(
      `hands staying very still (${durationOf('low_gesture')} seconds`
    )
    expect(SHORT_VIDEO_WARNING).toContain(
      `expression barely changing (${durationOf('flat_expression')} seconds)`
    )
  })

  it('says the recommended number of pictures a second, whatever it is', () => {
    expect(ANALYSIS_FPS_WARNING).toContain(`tested at ${DEFAULT_SETTINGS.analysisFps} pictures`)
  })

  /** Written for somebody practising for an interview, not for the people who built it. */
  it('uses none of the words that made the first version hard to read', () => {
    for (const warning of [SHORT_VIDEO_WARNING, ANALYSIS_FPS_WARNING]) {
      for (const word of ['frame', 'floor', 'findings are only reported', 'a second of analysis']) {
        expect(warning.toLowerCase()).not.toContain(word)
      }
    }
  })
})
