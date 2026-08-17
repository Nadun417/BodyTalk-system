import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

/**
 * The screen for reviewing a session's report and saving it as a PDF.
 * Producing the actual PDF is written later; this is the screen around it.
 */
export default function Report(): JSX.Element {
  const { id } = useParams()
  const sessionId = Number(id)
  const navigate = useNavigate()
  const [message, setMessage] = useState<string | null>(null)

  const exportPdf = async (): Promise<void> => {
    const res = await window.bodytalk.exportReport(sessionId)
    if (res.cancelled) return
    setMessage(res.error ?? 'Report saved.')
  }

  return (
    <div>
      <a className="back" onClick={() => navigate(`/dashboard/${sessionId}`)}>
        ← Dashboard
      </a>
      <h1 style={{ marginTop: 12 }}>Export report</h1>
      <p className="subtitle">
        Generates a styled PDF (summary, charts, event table, recommendations) saved wherever you
        choose — fully offline.
      </p>
      <button className="primary" onClick={exportPdf}>
        Save PDF…
      </button>
      {message && (
        <div className="empty" style={{ marginTop: 16 }}>
          {message}
        </div>
      )}
    </div>
  )
}
