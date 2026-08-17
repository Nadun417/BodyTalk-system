import { Routes, Route, NavLink } from 'react-router-dom'
import Home from './screens/Home'
import Upload from './screens/Upload'
import Processing from './screens/Processing'
import Dashboard from './screens/Dashboard'
import Report from './screens/Report'

export default function App(): JSX.Element {
  return (
    <div className="app">
      <header className="app-header">
        <NavLink to="/" className="brand">
          BodyTalk
        </NavLink>
        <span className="tagline">Private, on-device interview body-language coaching</span>
      </header>
      <main className="app-main">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/upload" element={<Upload />} />
          <Route path="/processing/:id" element={<Processing />} />
          <Route path="/dashboard/:id" element={<Dashboard />} />
          <Route path="/report/:id" element={<Report />} />
        </Routes>
      </main>
    </div>
  )
}
