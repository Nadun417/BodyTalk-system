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
 * The values a setting can be picked from, in order, for the lists on the settings screen.
 *
 * Offering a list rather than a box to type in means an impossible value can never be entered
 * in the first place. A value stored before the lists existed need not fall on one of the
 * steps, 57 seconds for instance, so it is added to the list rather than the list silently
 * showing something other than what is actually in use.
 */
export function settingChoices(name: keyof typeof SETTING_RANGES, current?: number): number[] {
  const { min, max, step } = SETTING_RANGES[name]
  const values: number[] = []
  for (let v = min; v <= max; v += step) values.push(v)
  if (current !== undefined && Number.isFinite(current) && !values.includes(current)) {
    values.push(current)
    values.sort((a, b) => a - b)
  }
  return values
}

/**
 * Why a shorter video is worth a second thought, said in everyday words and built from the
 * rules themselves.
 *
 * A finding is only reported when the behaviour behind it lasted long enough to be worth
 * mentioning. The longest of those waits is thirty seconds, for hands held still, and the next
 * is twenty, for an expression that barely changes. On a video near the thirty second floor
 * those two can hardly ever be reported, so a short video can look better than it really was.
 * That last point is the one a person needs, so the sentence ends on it.
 *
 * The first version of this sentence was accurate and hard to read ("Findings are only reported
 * when the behaviour lasted a while. The longest needs 30 seconds in a row..."), and the person
 * it was written for said so. It is shown only when the setting is below the recommended value,
 * which is when it applies.
 */
export const SHORT_VIDEO_WARNING =
  'Shorter videos give BodyTalk less to go on. Two things it looks for need a long stretch to ' +
  'show up: your hands staying very still (30 seconds in a row) and your expression barely ' +
  'changing (20 seconds). On a short video they may never appear, so fewer findings does not ' +
  'always mean it went better.'

/**
 * What changing how many pictures are checked each second costs, for the same reason and in the
 * same plain words. Shown only when the setting is not the recommended 6.
 */
export const ANALYSIS_FPS_WARNING =
  'BodyTalk was set up and tested at 6 pictures a second. At any other setting your results may ' +
  'come out differently, and they cannot be fairly compared with videos analysed at 6.'
