/**
 * Which theme the app is drawn in, and how that is decided.
 *
 * There are three choices rather than two. Light and dark are what they say. "Match Windows"
 * follows whatever Windows is set to, and keeps following it if Windows changes while the app
 * is open, which is what most people expect a desktop app to do without being asked.
 *
 * What is stored is the choice, not the result. Somebody who picked "Match Windows" in the
 * evening should not find the app stuck on dark the next morning because dark was what it
 * happened to be when they chose.
 *
 * The choice is kept in the browser's own storage rather than the database. It is a preference
 * about this screen on this machine, it does not belong with the analysis results, and it has
 * to be read before anything is drawn rather than after a message to the backend comes back.
 */

export type ThemeChoice = 'light' | 'dark' | 'system'
export type Theme = 'light' | 'dark'

const KEY = 'theme'

/**
 * The stored choice, or "Match Windows" when there is none.
 *
 * Earlier versions stored "light" or "dark", and those are still valid choices, so anybody who
 * already picked one keeps it. Only somebody who never chose starts on "Match Windows".
 */
export function parseChoice(stored: string | null | undefined): ThemeChoice {
  return stored === 'light' || stored === 'dark' || stored === 'system' ? stored : 'system'
}

export function readChoice(): ThemeChoice {
  try {
    return parseChoice(localStorage.getItem(KEY))
  } catch {
    return 'system'
  }
}

export function saveChoice(choice: ThemeChoice): void {
  try {
    localStorage.setItem(KEY, choice)
  } catch {
    // Not being able to remember the choice costs one click next time, which is not worth
    // interrupting anybody over.
  }
}

/** The theme actually drawn, given the choice and what Windows is currently set to. */
export function effectiveTheme(choice: ThemeChoice, windowsIsDark: boolean): Theme {
  if (choice === 'system') return windowsIsDark ? 'dark' : 'light'
  return choice
}

/** What each choice is called, for its tooltip and for anybody using a screen reader. */
export const CHOICE_NAME: Record<ThemeChoice, string> = {
  light: 'Light',
  dark: 'Dark',
  system: 'Match Windows'
}
