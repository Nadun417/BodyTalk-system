import { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import type { Session } from '@shared/types'
import { clock, shortDate, band } from '../lib/format'

/**
 * The opening screen: previous practice sessions, and the way in to a new one.
 *
 * Past sessions are listed rather than tucked away because the point of practising is seeing
 * whether anything changed between attempts. The three figures across the top exist for the
 * same reason: on their own a single score means very little, and what someone actually wants
 * to know is whether this attempt was better than the last one.
 */
export default function Home(): JSX.Element {
  const [sessions, setSessions] = useState<Session[]>([])
  const [loaded, setLoaded] = useState(false)
  const navigate = useNavigate()

  const refresh = useCallback(() => {
    window.bodytalk.listSessions().then((all) => {
      setSessions(all)
      setLoaded(true)
    })
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  const remove = async (id: number): Promise<void> => {
    // The backend asks the user to confirm before it deletes anything, so this can come back
    // having done nothing at all. Only reload the list when something actually went.
    const outcome = await window.bodytalk.deleteSession(id)
    if (outcome.deleted) refresh()
  }

  // Only finished sessions count towards the figures. A cancelled or failed run has no score
  // to average, and including them as zeros would make the summary say something false.
  const scored = sessions
    .filter((s) => s.status === 'complete' && s.overallScore !== null)
    .map((s) => s.overallScore as number)
  const best = scored.length ? Math.max(...scored) : null
  const average = scored.length
    ? Math.round((scored.reduce((a, b) => a + b, 0) / scored.length) * 10) / 10
    : null

  return (
    <main className="page">
      <div className="between">
        <div>
          <h1>Your practice sessions</h1>
          <p className="subtitle">
            Review your body-language coaching sessions and track progress.
          </p>
        </div>
        <button className="primary" onClick={() => navigate('/upload')}>
          + New analysis
        </button>
      </div>

      <div className="stats">
        <div className="stat">
          <div className="label">Sessions</div>
          <div className="stat-value">{sessions.length}</div>
        </div>
        <div className="stat">
          <div className="label">Best score</div>
          <div className="stat-value">{best ?? '—'}</div>
        </div>
        <div className="stat">
          <div className="label">Average</div>
          <div className="stat-value">{average ?? '—'}</div>
        </div>
      </div>

      <h2 style={{ margin: '22px 0 12px' }}>Recent sessions</h2>

      {!loaded ? null : sessions.length === 0 ? (
        <div className="empty">
          No sessions yet. Analyse a practice video and it will appear here.
        </div>
      ) : (
        sessions.map((s) => (
          <SessionRow key={s.id} session={s} onOpen={navigate} onDelete={remove} />
        ))
      )}

      {/*
        A way to exercise the whole path from the interface down to Python and back without
        needing a video or the detection libraries. It is genuinely useful while building and
        has no place in front of a user, so it only exists while developing and is not in the
        app that gets packaged.
      */}
      {import.meta.env.DEV && (
        <button
          className="ghost"
          style={{ marginTop: 20, fontSize: 12 }}
          onClick={async () => {
            const res = await window.bodytalk.createSession({
              videoPath: 'selftest.mp4',
              fusionMode: 'adaptive'
            })
            if (res.sessionId) {
              navigate(`/processing/${res.sessionId}`, {
                state: { selfTest: true, fusionMode: 'adaptive' }
              })
            }
          }}
        >
          Run pipeline self-test
        </button>
      )}
    </main>
  )
}

function SessionRow({
  session,
  onOpen,
  onDelete
}: {
  session: Session
  onOpen: (to: string) => void
  onDelete: (id: number) => void
}): JSX.Element {
  const finished = session.status === 'complete'
  return (
    <div className="session">
      <div className={`score-tile ${band(session.overallScore)}`}>
        <div className="label">Score</div>
        <div className="n">{session.overallScore ?? '—'}</div>
      </div>

      <div className="session-main">
        <div className="session-title">
          {shortDate(session.createdAt)}
          {session.videoDurationS > 0 && (
            <span className="muted" style={{ fontWeight: 400 }}>
              {' · '}
              {clock(session.videoDurationS)}
            </span>
          )}
        </div>
        <div className="row" style={{ margin: '6px 0 4px' }}>
          <span className={`badge ${session.fusionMode}`}>
            {session.fusionMode === 'adaptive' ? 'Adaptive' : 'Fixed'}
          </span>
          <span className="muted" style={{ fontSize: 13 }}>
            {session.fusionMode === 'adaptive' ? 'recommended' : 'for evaluation'}
          </span>
          {!finished && <span className="badge plain">{session.status}</span>}
        </div>
        <div className="session-file">{session.videoFilename}</div>
      </div>

      <button
        className="soft"
        disabled={!finished}
        onClick={() => onOpen(`/dashboard/${session.id}`)}
      >
        Open
      </button>
      <button className="ghost" onClick={() => onDelete(session.id)}>
        Delete
      </button>
    </div>
  )
}
