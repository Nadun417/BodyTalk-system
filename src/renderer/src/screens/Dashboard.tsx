import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import type { ScoredChannel } from '@shared/types'
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

  const { session, windows, events, recommendations } = detail
  const channels: ScoredChannel[] = ['face', 'pose', 'hands']

  /**
   * How many stretches of video were actually scored.
   *
   * Not the number of rows. Each window is stored as four of them, one for each of the three
   * channels plus the combined result, so counting rows claims four times as much analysis as
   * happened. What makes a window one window is the moment it starts, so the distinct start
   * times are the honest count.
   */
  const windowCount = new Set(windows.map((w) => w.tStartS)).size

  /**
   * The score for one channel, as the analysis worked it out.
   *
   * This used to be averaged here from the per-window scores, and it was wrong. A window
   * where the channel could not be measured has no score at all, and adding those in as
   * though they were zeros pulled the figure down. On a real run it reported 92 for hands
   * where the analysis had calculated 93, and a channel genuinely out of shot for a longer
   * stretch would have been understated far more heavily. Since that is precisely the case
   * the weighting exists to handle, showing it as poor performance would have undermined
   * the point of the whole thing.
   *
   * An em-dash means nothing was recorded, which is true of sessions analysed before these
   * scores were stored.
   */
  const channelScore = (ch: ScoredChannel): string => {
    const score = session.channelScores[ch]
    return score === null || score === undefined ? '—' : score.toString()
  }

  return (
    <div>
      <a className="back" onClick={() => navigate('/')}>
        ← History
      </a>
      <h1 style={{ marginTop: 12 }}>{session.videoFilename}</h1>
      <p className="subtitle">
        {session.fusionMode} fusion · {windowCount} windows · {session.status}
      </p>

      {/*
        The analysis writes this sentence itself, from the same findings the rest of the
        screen is built from. It is shown rather than re-worded here so that the summary,
        the scores and the advice below cannot drift into telling three different stories.
      */}
      {session.overallSummary && (
        <p className="summary" style={{ marginTop: -4, marginBottom: 16 }}>
          {session.overallSummary}
        </p>
      )}

      <div className="cards">
        <div className="card">
          <div className="label">Overall</div>
          <div className="score">{session.overallScore ?? '—'}</div>
        </div>
        {channels.map((ch) => (
          <div className="card" key={ch}>
            <div className="label">{ch}</div>
            <div className="score">{channelScore(ch)}</div>
          </div>
        ))}
      </div>

      <WeightOverTimeChart windows={windows} fusionMode={session.fusionMode} />

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

      {/*
        Advice comes last, after the observations it was drawn from, because that is the
        order it makes sense in: here is what was seen, and here is what to do about it.
        Every one of these was built from events in the list above rather than from any
        judgement about the person, which is why the two sit on the same screen.
      */}
      {recommendations.length > 0 && (
        <>
          <h2 style={{ fontSize: 16, marginTop: 24 }}>What to work on next</h2>
          {recommendations.map((r) => (
            <div className="event" key={r.rank}>
              <strong>{r.title}</strong>
              <div className="label" style={{ marginTop: 4 }}>
                {r.body}
              </div>
            </div>
          ))}
        </>
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
