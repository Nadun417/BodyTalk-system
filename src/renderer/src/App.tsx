import { useEffect, useState } from 'react'
import { Routes, Route, Link } from 'react-router-dom'
import Home from './screens/Home'
import Upload from './screens/Upload'
import Processing from './screens/Processing'
import Dashboard from './screens/Dashboard'
import Report from './screens/Report'

type Theme = 'light' | 'dark'

/**
 * Remember which theme was chosen, between runs of the app.
 *
 * Kept in the browser's own storage rather than in the database. It is a preference about
 * this screen on this machine, it does not belong with the analysis results, and reading it
 * needs to happen before anything is drawn rather than after a message to the backend comes
 * back. Losing it costs the user one click.
 */
function storedTheme(): Theme {
  try {
    return localStorage.getItem('theme') === 'dark' ? 'dark' : 'light'
  } catch {
    return 'light'
  }
}

export default function App(): JSX.Element {
  const [theme, setTheme] = useState<Theme>(storedTheme)

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    try {
      localStorage.setItem('theme', theme)
    } catch {
      // Not being able to remember the choice is not worth interrupting anyone over.
    }
  }, [theme])

  return (
    <div className="app">
      <header className="topbar">
        <Link to="/" className="logo">
          <span className="logo-mark">B</span>
          <span className="logo-word">BodyTalk</span>
        </Link>
        <div className="topbar-spacer" />
        <button
          className="icon-button"
          onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')}
          title={theme === 'light' ? 'Switch to a dark screen' : 'Switch to a light screen'}
          aria-label="Switch between the light and dark screen"
        >
          {theme === 'light' ? '☾' : '☀'}
        </button>
      </header>

      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/upload" element={<Upload />} />
        <Route path="/processing/:id" element={<Processing />} />
        <Route path="/dashboard/:id" element={<Dashboard />} />
        <Route path="/report/:id" element={<Report />} />
      </Routes>
    </div>
  )
}
