import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import type { SessionDetail } from '../../../preload/index'
import ScoresOverTimeChart from '../components/charts/ScoresOverTimeChart'
import WeightOverTimeChart from '../components/charts/WeightOverTimeChart'
import { buildReportDocDefinition } from '../report/pdfReport'
import { renderPdf } from '../report/makePdf'
import { clock, shortDate, CHANNEL_NAME } from '../lib/format'

/**
 * The screen for saving a session as a PDF.
 *
 * It says what the document will contain before it is made, because the user is about to
 * choose where to put a file and it is fair to know what is going into it. The panel on the
 * left is a sketch of the page rather than a real preview: it shows the shape of what comes
 * out, and drawing the document twice, once here and once in the file, would be work spent
 * making the two disagree.
 *
 * The two charts are drawn on this screen as well, off to the side where they cannot be seen,
 * purely so they can be captured as pictures for the document. Drawing them again in the PDF
 * from scratch would mean a second implementation of both charts that could drift away from
 * the ones on the results screen and quietly start telling a different story.
 */
export default function Report(): JSX.Element {
  const { id } = useParams()
  const sessionId = Number(id)
  const navigate = useNavigate()
  const [detail, setDetail] = useState<SessionDetail | null>(null)
  const [message, setMessage] = useState<{ tone: 'ok' | 'warn' | 'bad'; text: string } | null>(null)
  const [saving, setSaving] = useState(false)
  const offscreen = useRef<HTMLDivElement>(null)

  useEffect(() => {
    window.bodytalk.getSession(sessionId).then(setDetail)
  }, [sessionId])

  /**
   * Take a picture of each chart as it has just been drawn.
   *
   * A chart lives on a canvas, and a canvas can hand over what it is showing as an image,
   * which is exactly what a PDF needs. If either one is missing the report still gets made
   * and says so in place of the chart, because a document that arrives without a section it
   * promised is worse than one that explains the gap.
   */
  const captureCharts = (): { scores?: string; weights?: string } => {
    const canvases = offscreen.current?.querySelectorAll('canvas') ?? []
    const png = (canvas?: HTMLCanvasElement): string | undefined => {
      try {
        return canvas ? canvas.toDataURL('image/png') : undefined
      } catch {
        return undefined
      }
    }
    return { scores: png(canvases[0]), weights: png(canvases[1]) }
  }

  const save = async (): Promise<void> => {
    if (!detail) return
    setMessage(null)
    setSaving(true)
    try {
      const doc = buildReportDocDefinition({
        session: detail.session,
        events: detail.events,
        recommendations: detail.recommendations,
        windowCount: new Set(detail.windows.map((w) => w.tStartS)).size,
        charts: captureCharts()
      })
      const bytes = await renderPdf(doc)
      const res = await window.bodytalk.exportReport(sessionId, bytes)
      if (res.cancelled) return
      if (res.error) setMessage({ tone: 'bad', text: res.error })
      else setMessage({ tone: 'ok', text: `Saved to ${res.savedTo}` })
    } catch (err) {
      setMessage({ tone: 'bad', text: `The report could not be made: ${(err as Error).message}` })
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
              <div style={{ fontWeight: 650 }}>Practice session report</div>
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
              'Both charts, as they appear on the results screen',
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
                {saving ? 'Making the PDF…' : 'Save PDF…'}
              </button>
              <button className="soft" onClick={() => navigate(`/dashboard/${sessionId}`)}>
                Back to results
              </button>
            </div>

            {message && (
              <div className={`notice ${message.tone}`} style={{ marginTop: 14 }}>
                {message.text}
              </div>
            )}
          </div>
        </div>
      </div>

      {/*
        The charts, drawn at the width they are wanted at in the document and parked out of
        sight. They are not hidden with display:none, because a chart that is never laid out is
        never drawn, and an undrawn chart has nothing to photograph.
      */}
      {detail && (
        <div
          ref={offscreen}
          aria-hidden
          // Marked as light because these are going onto white paper, whichever theme the
          // app itself is showing.
          data-theme="light"
          style={{ position: 'fixed', left: -10000, top: 0, width: 900 }}
        >
          <div style={{ width: 900, height: 320, background: '#fff' }}>
            <ScoresOverTimeChart windows={detail.windows} forExport />
          </div>
          <div style={{ width: 900, height: 300, background: '#fff' }}>
            <WeightOverTimeChart
              windows={detail.windows}
              fusionMode={detail.session.fusionMode}
              forExport
            />
          </div>
        </div>
      )}
    </main>
  )
}
