import { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import type { Session } from '@shared/types'

/**
 * The opening screen: previous practice sessions, and the way in to a new one.
 *
 * Past sessions are listed rather than tucked away because the point of practising is
 * seeing whether anything changed between attempts.
 */
export default function Home(): JSX.Element {
  const [sessions, setSessions] = useState<Session[]>([])
  const navigate = useNavigate()

  const refresh = useCallback(() => {
    window.bodytalk.listSessions().then(setSessions)
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  const runSelfTest = async (): Promise<void> => {
    // Dev affordance: exercises the bridge → DB → dashboard path with no MediaPipe.
    const res = await window.bodytalk.createSession({
      videoPath: 'selftest.mp4',
      fusionMode: 'adaptive'
    })
    if (res.sessionId) {
      navigate(`/processing/${res.sessionId}`, {
        state: { selfTest: true, fusionMode: 'adaptive' }
      })
    }
  }

  const remove = async (id: number): Promise<void> => {
    // The backend asks the user to confirm before it deletes anything, so this can come
    // back having done nothing at all. Only reload the list when something actually went.
    const outcome = await window.bodytalk.deleteSession(id)
    if (outcome.deleted) refresh()
  }

  return (
    <div>
      <h1>Your practice sessions</h1>
      <p className="subtitle">Everything here stays on this device. Nothing is uploaded.</p>

      <div className="row" style={{ marginBottom: 20 }}>
        <button className="primary" onClick={() => navigate('/upload')}>
          New analysis
        </button>
        <button onClick={runSelfTest} title="Runs the dependency-free pipeline self-test">
          Run pipeline self-test (dev)
        </button>
      </div>

      {sessions.length === 0 ? (
        <div className="empty">No sessions yet. Start a new analysis to see feedback here.</div>
      ) : (
        sessions.map((s) => (
          <div className="history-item" key={s.id}>
            <div>
              <div>{s.videoFilename}</div>
              <div className="label">
                {new Date(s.createdAt).toLocaleString()} · {s.fusionMode} · {s.status}
              </div>
            </div>
            <div className="row">
              <span className="score" style={{ fontSize: 20 }}>
                {s.overallScore ?? '—'}
              </span>
              <button onClick={() => navigate(`/dashboard/${s.id}`)}>Open</button>
              <button onClick={() => remove(s.id)}>Delete</button>
            </div>
          </div>
        ))
      )}
    </div>
  )
}
