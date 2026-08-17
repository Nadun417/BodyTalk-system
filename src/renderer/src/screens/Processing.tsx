import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams, useLocation } from 'react-router-dom'
import type { FusionMode, ProgressUpdate } from '@shared/types'

interface ProcessingState {
  selfTest?: boolean
  fusionMode?: FusionMode
  videoPath?: string
}

/**
 * The screen shown while a video is being analysed.
 *
 * The progress shown is the real count of frames processed, not an animation running on a
 * timer. Analysis can take several minutes, and a bar that is honestly slow is easier to
 * wait through than one that races to ninety percent and then stops. Cancelling actually
 * stops the work rather than just hiding it.
 */
export default function Processing(): JSX.Element {
  const { id } = useParams()
  const sessionId = Number(id)
  const navigate = useNavigate()
  const state = (useLocation().state ?? {}) as ProcessingState
  const [progress, setProgress] = useState<ProgressUpdate | null>(null)
  const [error, setError] = useState<string | null>(null)
  const started = useRef(false)

  useEffect(() => {
    const unsubscribe = window.bodytalk.onProgress((p) => {
      if (p.sessionId === sessionId) setProgress(p)
    })

    // Guard against React StrictMode's double-invoke in dev.
    if (!started.current) {
      started.current = true
      window.bodytalk
        .startAnalysis({
          sessionId,
          fusionMode: state.fusionMode ?? 'adaptive',
          videoPath: state.videoPath,
          selfTest: state.selfTest
        })
        .then(() => navigate(`/dashboard/${sessionId}`, { replace: true }))
        .catch((e: Error) => {
          if (e.message !== 'cancelled') setError(e.message)
          else navigate('/', { replace: true })
        })
    }

    return unsubscribe
  }, [sessionId])

  const pct =
    progress && progress.total > 0 ? Math.round((progress.done / progress.total) * 100) : 0

  return (
    <div>
      <h1>Analysing…</h1>
      <p className="subtitle">{progress?.stage ?? 'Starting the on-device pipeline'}</p>

      <div className="card">
        <div className="progress-track">
          <div className="progress-fill" style={{ width: `${pct}%` }} />
        </div>
        <div className="label" style={{ marginTop: 10 }}>
          {progress ? `${progress.done} / ${progress.total} frames · ${pct}%` : 'Initialising…'}
        </div>
      </div>

      {error && (
        <div className="empty" style={{ color: '#ff8b8b', marginTop: 16 }}>
          {error}
        </div>
      )}

      <div className="row" style={{ marginTop: 16 }}>
        <button onClick={() => window.bodytalk.cancelAnalysis(sessionId)}>Cancel</button>
        {error && <button onClick={() => navigate('/')}>Back to history</button>}
      </div>
    </div>
  )
}
