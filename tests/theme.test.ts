import { describe, it, expect } from 'vitest'
import { CHOICE_NAME, effectiveTheme, parseChoice } from '../src/renderer/src/lib/theme'

/**
 * Which theme the app is drawn in.
 *
 * The app used to offer light and dark only, starting on light. It now also follows Windows,
 * and starts there for anybody who never chose. The case that matters most is the one that is
 * easy to break without noticing: somebody who picked a theme before the change must keep it.
 */
describe('the theme', () => {
  it('keeps a choice made before "Match Windows" existed', () => {
    expect(parseChoice('light')).toBe('light')
    expect(parseChoice('dark')).toBe('dark')
  })

  it('starts on "Match Windows" for anybody who never chose', () => {
    expect(parseChoice(null)).toBe('system')
    expect(parseChoice(undefined)).toBe('system')
  })

  it('treats anything unrecognised as not having chosen', () => {
    expect(parseChoice('')).toBe('system')
    expect(parseChoice('purple')).toBe('system')
  })

  it('follows Windows only when asked to', () => {
    expect(effectiveTheme('system', true)).toBe('dark')
    expect(effectiveTheme('system', false)).toBe('light')
    // A definite choice wins over whatever Windows is doing.
    expect(effectiveTheme('light', true)).toBe('light')
    expect(effectiveTheme('dark', false)).toBe('dark')
  })

  it('names every choice in words, for the tooltip and for screen readers', () => {
    expect(CHOICE_NAME).toEqual({ light: 'Light', dark: 'Dark', system: 'Match Windows' })
  })
})
