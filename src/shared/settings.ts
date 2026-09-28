import type { AppSettings } from './types'

/**
 * What the changeable settings are allowed to be, and what they are when nobody has changed
 * them.
 *
 * Both halves of the app read this file. The settings screen uses it to bound its inputs and
 * to say what the allowed range is, and the backend uses it to check anything on its way into
 * the database. Neither trusts the other: a screen that lets somebody type 5000 frames a
 * second is a nuisance, but a database holding 5000 frames a second is a run that never
 * finishes, and the screen is not the only thing that can write to the database.
 *
 * The analysis itself keeps its own copy of the length limits, because it has to work when it
 * is run from the terminal with no application around it. If either side changes, the other
 * has to change with it.
 */

export const DEFAULT_SETTINGS: AppSettings = {
  analysisFps: 6,
  reportSavePath: null,
  // Shortest video accepted. Moved from sixty seconds to fifty-five on 20 September 2026,
  // after the first recordings supplied by somebody other than the author all landed between
  // 57 and 60 seconds and were refused over margins as small as three tenths of a second.
  minDurationS: 55
}

/**
 * The range each number may take.
 *
 * The lengths are the range the design allows, and the analysis clamps to the same two
 * numbers. The frame rate is narrower than it looks: the measurements were all set up at six
 * frames a second, and every threshold assumes that many samples in a second of analysis.
 * Five to ten is the range the design offered, so it is what the screen offers, but the screen
 * says plainly what changing it costs.
 */
export const SETTING_RANGES = {
  minDurationS: { min: 30, max: 180, step: 5 },
  analysisFps: { min: 5, max: 10, step: 1 }
} as const

/**
 * Put `value` inside the allowed range, or give the normal setting when there is no answer.
 *
 * An empty box on the screen, an empty row in the table and a word where a number should be
 * all mean the same thing: nobody has chosen, so the normal setting stands. A zero is
 * different. It is a real answer, just an unusable one, so it is pulled up to the lowest
 * allowed value like any other number below the range.
 */
export function clampSetting(name: keyof typeof SETTING_RANGES, value: unknown): number {
  const blank =
    value === null || value === undefined || (typeof value === 'string' && value.trim() === '')
  if (blank) return DEFAULT_SETTINGS[name]
  const n = Number(value)
  if (!Number.isFinite(n)) return DEFAULT_SETTINGS[name]
  const range = SETTING_RANGES[name]
  return Math.min(range.max, Math.max(range.min, n))
}

/**
 * The reason a short video is worth warning about, written from the rules themselves.
 *
 * A finding is only reported when the behaviour behind it lasted long enough to be worth
 * mentioning. The longest of those waits is thirty seconds, so on a video near the thirty
 * second floor it can essentially never be reported, and the twenty second one barely can.
 * The sentence is kept here rather than in the screen because it is a fact about the analysis,
 * and the settings screen is not the only place it might need to be said.
 */
export const SHORT_VIDEO_WARNING =
  'Findings are only reported when the behaviour lasted a while. The longest needs 30 seconds ' +
  'in a row, and a still expression needs 20. A recording near the 30 second floor can barely ' +
  'produce either, so it will look quieter than a longer one rather than better.'

/** What changing the frame rate costs, said in the same place for the same reason. */
export const ANALYSIS_FPS_WARNING =
  'Every measurement was set up at 6 frames a second. At any other rate a second of analysis ' +
  'is built from a different number of frames, so findings can come out differently and the ' +
  'scores cannot be compared with sessions analysed at 6.'
