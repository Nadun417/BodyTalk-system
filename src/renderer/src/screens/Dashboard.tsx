import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import type { Channel } from '@shared/types'
import type { SessionDetail } from '../../../preload/index'
import WeightOverTimeChart from '../components/charts/WeightOverTimeChart'

/**
 * The results screen: overall and per-channel scores, the charts, and the list of moments
 * worth looking at. Selecting one of those moments jumps the video to it, so the user can
 * see the behaviour for themselves rather than taking the score's word for it.
 */
export default function Dashboard(): JSX.Element {
  const { id } = useParams()
  const sessionId = Number(id)
  const navigate = useNavigate()
  const [detail, setDetail] = useState<SessionDetail | null>(null)

  useEffect(() => {
    window.bodytalk.getSession(sessionId).then(setDetail)
  }, [sessionId])

  if (!detail) return <div className="empty">Loading…</div>

  const { session, windows, events } = detail
  const channels: Channel[] = ['face', 'pose', 'hands']
  const channelAvg = (ch: Channel): string => {
    const xs = windows.filter((w) => w.channel === ch).map((w) => w.rawScore)
    return xs.length ? Math.round(xs.reduce((a, b) => a + b, 0) / xs.length).toString() : '—'
  }

  return (
    <div>
      <a className="back" onClick={() => navigate('/')}>
        ← History
      </a>
      <h1 style={{ marginTop: 12 }}>{session.videoFilename}</h1>
      <p className="subtitle">
        {session.fusionMode} fusion · {windows.length} windows · {session.status}
      </p>

      <div className="cards">
        <div className="card">
          <div className="label">Overall</div>
          <div className="score">{session.overallScore ?? '—'}</div>
        </div>
        {channels.map((ch) => (
          <div className="card" key={ch}>
            <div className="label">{ch}</div>
            <div className="score">{channelAvg(ch)}</div>
          </div>
        ))}
      </div>

      <WeightOverTimeChart windows={windows} />

      <h2 style={{ fontSize: 16 }}>Timestamped insights</h2>
      {events.length === 0 ? (
        <div className="empty">No notable events detected.</div>
      ) : (
        events.map((e, i) => (
          <div className="event" key={i}>
            <span className="ts">
              {fmt(e.tStartS)}–{fmt(e.tEndS)}
            </span>
            <strong>{e.channel}</strong> — {e.message}
            <div className="label" style={{ marginTop: 4 }}>
              {e.suggestion}
            </div>
          </div>
        ))
      )}

      <div className="row" style={{ marginTop: 20 }}>
        <button className="primary" onClick={() => navigate(`/report/${sessionId}`)}>
          Export report
        </button>
      </div>
    </div>
  )
}

function fmt(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${String(s).padStart(2, '0')}`
}
