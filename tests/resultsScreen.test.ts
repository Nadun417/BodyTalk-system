import { describe, it, expect } from 'vitest'
import type { AnalysisEvent } from '../src/shared/types'
import { FINDING_NAME, groupFindings, howOften } from '../src/renderer/src/lib/findings'
import { BAND_WORD, SCORE_LEGEND, band, wholeScore } from '../src/renderer/src/lib/format'

/**
 * The parts of the results screen that decide what the reader sees, tested away from the screen.
 *
 * The screen was rebuilt after the person it was for found it hard to read. The two things that
 * made the biggest difference are here: repeated findings shown once with every time they
 * happened, and a word under each score saying what the number means.
 */

const at = (
  type: string,
  start: number,
  end: number,
  severity: AnalysisEvent['severity'] = 'low',
  channel: AnalysisEvent['channel'] = 'face'
): AnalysisEvent => ({
  tStartS: start,
  tEndS: end,
  channel,
  type,
  severity,
  message: `${type} from ${start} to ${end}.`,
  suggestion: `Tip for ${type} at ${start}.`
})

describe('grouping findings', () => {
  /**
   * The case that prompted it: on a real session one finding appeared five times in a row,
   * each with the same tip underneath.
   */
  it('shows a finding that happened five times as one line, with all five times', () => {
    const events = [9, 117, 141, 173, 203].map((s) => at('head_movement', s, s + 5))
    const groups = groupFindings(events)
    expect(groups).toHaveLength(1)
    expect(groups[0].moments.map((m) => m.tStartS)).toEqual([9, 117, 141, 173, 203])
    expect(groups[0].name).toBe(FINDING_NAME.head_movement)
  })

  it('says the tip once, taken from the first time it happened', () => {
    const groups = groupFindings([at('head_movement', 50, 55), at('head_movement', 10, 15)])
    expect(groups[0].tip).toBe('Tip for head_movement at 10.')
  })

  it('adds up how long it went on for, in whole seconds', () => {
    const groups = groupFindings([
      at('head_movement', 0, 4.4),
      at('head_movement', 10, 13.3),
      at('head_movement', 20, 25)
    ])
    expect(groups[0].totalS).toBe(13)
    expect(howOften(groups[0])).toBe('3 times, 13 seconds in all')
  })

  it('says once, and not "1 times"', () => {
    expect(howOften(groupFindings([at('slouching', 0, 8)])[0])).toBe('Once, for 8 seconds')
    expect(howOften(groupFindings([at('hand_to_face', 0, 1)])[0])).toBe('Once, for 1 second')
  })

  /**
   * A list in time order put a good moment at 0:05 above a real problem at 1:40, and a reader
   * skimming the top of it got the wrong picture.
   */
  it('lists what to work on first, what is worth knowing next, and what went well last', () => {
    const groups = groupFindings([
      at('smile', 5, 7, 'info'),
      at('hands_out_of_frame', 10, 30, 'info', 'hands'),
      at('head_movement', 60, 66, 'low'),
      at('looking_away', 100, 105, 'medium')
    ])
    expect(groups.map((g) => g.type)).toEqual([
      'looking_away',
      'head_movement',
      'hands_out_of_frame',
      'smile'
    ])
  })

  it('keeps every occurrence, so every one can still be jumped to', () => {
    const events = [
      at('head_movement', 1, 6),
      at('slouching', 2, 8),
      at('head_movement', 20, 25),
      at('smile', 30, 32, 'info')
    ]
    const total = groupFindings(events).reduce((n, g) => n + g.moments.length, 0)
    expect(total).toBe(events.length)
  })

  it('falls back to the message for a kind of finding it has no name for', () => {
    const groups = groupFindings([at('something_new', 0, 5)])
    expect(groups[0].name).toBe('something_new from 0 to 5.')
  })

  /**
   * The group names are said to the user, so they are held to the same rule as the messages:
   * nothing the measurement cannot see. The face is measured by the angle of the head, not by
   * where the eyes point.
   */
  it('never names a finding by something the analysis cannot see', () => {
    for (const name of Object.values(FINDING_NAME)) {
      const said = name.toLowerCase()
      for (const word of ['eye', 'looked', 'gaze', 'slouch', 'leaned', 'channel']) {
        expect(said).not.toContain(word)
      }
    }
  })
})

describe('what a score means', () => {
  it('puts a word under every score, from the bands the colours already use', () => {
    expect(BAND_WORD[band(90)]).toBe('Going well')
    expect(BAND_WORD[band(60)]).toBe('Mixed')
    expect(BAND_WORD[band(40)]).toBe('Worth a look')
    expect(BAND_WORD[band(null)]).toBe('')
  })

  it('explains the bands with the same edges the bands use', () => {
    expect(band(75)).toBe('good')
    expect(band(74)).toBe('fair')
    expect(band(55)).toBe('fair')
    expect(band(54)).toBe('poor')
    expect(SCORE_LEGEND).toContain('75 and above')
    expect(SCORE_LEGEND).toContain('55 to 74')
    expect(SCORE_LEGEND).toContain('under 55')
  })

  it('shows scores as whole numbers, and leaves a missing score missing', () => {
    expect(wholeScore(85.9)).toBe(86)
    expect(wholeScore(66.4)).toBe(66)
    expect(wholeScore(null)).toBe(null)
  })
})
