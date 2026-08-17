import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import type { FusionMode } from '@shared/types'

/**
 * The screen for choosing a practice video and starting an analysis.
 * Drag and drop, and the fuller checks on the chosen file, are added later.
 */
export default function Upload(): JSX.Element {
  const [videoPath, setVideoPath] = useState<string | null>(null)
  const [fusionMode, setFusionMode] = useState<FusionMode>('adaptive')
  const [error, setError] = useState<string | null>(null)
  const navigate = useNavigate()

  const pick = async (): Promise<void> => {
    const path = await window.bodytalk.openVideoDialog()
    if (path) {
      setVideoPath(path)
      setError(null)
    }
  }

  const start = async (): Promise<void> => {
    if (!videoPath) return
    const res = await window.bodytalk.createSession({ videoPath, fusionMode })
    if (res.error || !res.sessionId) {
      setError(res.error ?? 'Could not create session.')
      return
    }
    navigate(`/processing/${res.sessionId}`, {
      state: { videoPath, fusionMode, selfTest: false }
    })
  }

  return (
    <div>
      <a className="back" onClick={() => navigate('/')}>
        ← Back
      </a>
      <h1 style={{ marginTop: 12 }}>New analysis</h1>
      <p className="subtitle">
        Select a practice interview video (60–180s minimum). It is copied locally and never leaves
        your device.
      </p>

      <div className="card" style={{ marginBottom: 16 }}>
        <button onClick={pick}>Choose video…</button>
        <div className="label" style={{ marginTop: 10 }}>
          {videoPath ?? 'No file selected'}
        </div>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="label">Fusion mode</div>
        <div className="row" style={{ marginTop: 8 }}>
          <label>
            <input
              type="radio"
              checked={fusionMode === 'adaptive'}
              onChange={() => setFusionMode('adaptive')}
            />{' '}
            Adaptive (novelty)
          </label>
          <label>
            <input
              type="radio"
              checked={fusionMode === 'fixed'}
              onChange={() => setFusionMode('fixed')}
            />{' '}
            Fixed weighting, used for comparison
          </label>
        </div>
      </div>

      {error && (
        <div className="empty" style={{ color: '#ff8b8b' }}>
          {error}
        </div>
      )}

      <button className="primary" disabled={!videoPath} onClick={start}>
        Analyse
      </button>
    </div>
  )
}
