import { useEffect, useLayoutEffect, useState } from 'react'
import { Routes, Route, Link, NavLink } from 'react-router-dom'
import Home from './screens/Home'
import Upload from './screens/Upload'
import Processing from './screens/Processing'
import Dashboard from './screens/Dashboard'
import Report from './screens/Report'
import Settings from './screens/Settings'
import { GearIcon, MonitorIcon, MoonIcon, SunIcon } from './components/Icons'
import logoUrl from './assets/logo.png'
import { effectiveTheme, readChoice, saveChoice, CHOICE_NAME, type ThemeChoice } from './lib/theme'

/** Asks Windows, through the page, whether it is currently set to dark. */
const WINDOWS_DARK = '(prefers-color-scheme: dark)'

export default function App(): JSX.Element {
  const [choice, setChoice] = useState<ThemeChoice>(readChoice)
  const [windowsIsDark, setWindowsIsDark] = useState<boolean>(
    () => window.matchMedia?.(WINDOWS_DARK).matches ?? false
  )

  // Follow Windows while the app is open, so "Match Windows" keeps matching when Windows
  // switches between light and dark on its own schedule.
  useEffect(() => {
    const query = window.matchMedia?.(WINDOWS_DARK)
    if (!query) return
    const follow = (e: MediaQueryListEvent): void => setWindowsIsDark(e.matches)
    query.addEventListener('change', follow)
    return () => query.removeEventListener('change', follow)
  }, [])

  const theme = effectiveTheme(choice, windowsIsDark)

  // Before the screen is painted rather than after, so somebody on the dark theme does not see
  // a flash of the light one each time the app opens.
  useLayoutEffect(() => {
    const root = document.documentElement
    root.dataset.theme = theme
    // Tells the browser too, so its own parts, the scrollbars and the number boxes on the
    // settings screen, are drawn to match rather than staying light on a dark screen.
    root.style.colorScheme = theme
  }, [theme])

  const choose = (next: ThemeChoice): void => {
    setChoice(next)
    saveChoice(next)
  }

  return (
    <div className="app">
      <header className="topbar">
        <Link to="/" className="logo">
          {/* Made from the same picture as the Windows icon, so the two always match. Left
              without a description for screen readers, because the name is written beside it. */}
          <img className="logo-mark" src={logoUrl} alt="" width={32} height={32} />
          <span className="logo-word">BodyTalk</span>
        </Link>
        <div className="topbar-spacer" />
        <ThemeSwitch choice={choice} onChoose={choose} />
        {/* Labelled rather than a bare icon. Somebody practising for an interview should not
            have to guess what a symbol in the corner does. It is marked while its screen is
            open, so the top bar also says where you are. */}
        <NavLink
          to="/settings"
          className={({ isActive }) => `topbar-button${isActive ? ' active' : ''}`}
        >
          <GearIcon />
          <span>Settings</span>
        </NavLink>
      </header>

      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/upload" element={<Upload />} />
        <Route path="/processing/:id" element={<Processing />} />
        <Route path="/dashboard/:id" element={<Dashboard />} />
        <Route path="/report/:id" element={<Report />} />
        <Route path="/settings" element={<Settings />} />
      </Routes>
    </div>
  )
}

/**
 * Light, dark, or match Windows, as three small buttons side by side.
 *
 * It replaces a single button that swapped between light and dark. That button showed a moon
 * on the light screen and a sun on the dark one, which left it unclear whether the icon meant
 * "this is the theme you are on" or "press to get this one". Here the choice you are on is
 * filled in, so the switch shows where it stands, and each button names itself when hovered.
 */
function ThemeSwitch({
  choice,
  onChoose
}: {
  choice: ThemeChoice
  onChoose: (choice: ThemeChoice) => void
}): JSX.Element {
  const options: { value: ThemeChoice; icon: JSX.Element }[] = [
    { value: 'light', icon: <SunIcon /> },
    { value: 'dark', icon: <MoonIcon /> },
    { value: 'system', icon: <MonitorIcon /> }
  ]
  return (
    <div className="theme-switch" role="group" aria-label="How the app looks">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          aria-pressed={choice === o.value}
          aria-label={CHOICE_NAME[o.value]}
          title={CHOICE_NAME[o.value]}
          onClick={() => onChoose(o.value)}
        >
          {o.icon}
        </button>
      ))}
    </div>
  )
}
