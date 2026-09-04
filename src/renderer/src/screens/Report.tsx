import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import type { SessionDetail } from '../../../preload/index'
import { clock, shortDate, CHANNEL_NAME } from '../lib/format'

/**
 * The screen for saving a session as a PDF.
 *
 * It says what the document will contain before it is made, because the user is about to
 * choose where to put a file and it is fair to know what is going into it. The panel on the
 * left is a sketch of the page rather than a real preview: it shows the shape of what comes
 * out, and drawing the actual document twice, once here and once in the file, would be work
 * spent making the two disagree.
 */
export default function Report(): JSX.Element {
  const { id } = useParams()
  const sessionId = Number(id)
  const navigate = useNavigate()
  const [detail, setDetail] = useState<SessionDetail | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    window.bodytalk.getSession(sessionId).then(setDetail)
  }, [sessionId])

  const save = async (): Promise<void> => {
    setMessage(null)
    setSaving(true)
    try {
      const res = await window.bodytalk.exportReport(sessionId)
      if (res.cancelled) return
      setMessage(res.error ?? 'Report saved.')
    } finally {
      setSaving(false)
    }
  }

  const session = detail?.session
  const scores = session
    ? [
        session.overallScore,
        ...(['face', 'pose', 'hands'] as const).map((c) => session.channelScores[c])
      ]
    : []

  return (
    <main className="page narrow">
      <div className="center" style={{ margin: '18px 0 24px' }}>
        <h1>Your report</h1>
        <p className="subtitle">
          A PDF of this coaching session, saved wherever you choose. It never leaves your device.
        </p>
      </div>

      <div className="card">
        <div className="report-grid">
          <div className="page-preview">
            <div
              style={{
                background: 'var(--brand-soft)',
                borderRadius: 6,
                padding: '10px 12px',
                marginBottom: 14
              }}
            >
              <div style={{ color: 'var(--brand)', fontWeight: 700, fontSize: 11 }}>BodyTalk</div>
              <div style={{ fontWeight: 650 }}>Session report</div>
            </div>
            <div className="row" style={{ marginBottom: 14 }}>
              {scores.map((s, i) => (
                <span key={i} className="badge plain" style={{ fontSize: 13 }}>
                  {s ?? '—'}
                </span>
              ))}
            </div>
            <div
              style={{
                background: 'var(--surface-2)',
                borderRadius: 6,
                height: 74,
                marginBottom: 14
              }}
            />
            {[92, 100, 74, 96, 62].map((w, i) => (
              <div className="skeleton" key={i} style={{ width: `${w}%` }} />
            ))}
          </div>

          <div>
            <p className="label" style={{ marginBottom: 10 }}>
              What goes in
            </p>
            {[
              session
                ? `The session of ${shortDate(session.createdAt)}, ${clock(session.videoDurationS)} long`
                : 'The session details',
              'The overall score and each channel’s score',
              detail
                ? `${detail.events.length} timestamped observations`
                : 'The moments we noticed',
              detail
                ? `${detail.recommendations.length} suggestions to work on`
                : 'Suggestions to improve'
            ].map((line) => (
              <div className="row" key={line} style={{ marginBottom: 9, alignItems: 'flex-start' }}>
                <span className="tick">✓</span>
                <span>{line}</span>
              </div>
            ))}

            {detail && (
              <p className="muted" style={{ fontSize: 13, marginTop: 14 }}>
                Channels included:{' '}
                {(['face', 'pose', 'hands'] as const).map((c) => CHANNEL_NAME[c]).join(', ')}.
              </p>
            )}

            <div className="row" style={{ marginTop: 18 }}>
              <button className="primary" onClick={save} disabled={saving || !detail}>
                {saving ? 'Saving…' : 'Save PDF…'}
              </button>
              <button className="soft" onClick={() => navigate(`/dashboard/${sessionId}`)}>
                Back to results
              </button>
            </div>

            {message && (
              <div className="notice warn" style={{ marginTop: 14 }}>
                {message}
              </div>
            )}
          </div>
        </div>
      </div>
    </main>
  )
}
