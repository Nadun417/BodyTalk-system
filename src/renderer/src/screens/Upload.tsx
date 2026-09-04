import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import type { FusionMode, VideoValidation } from '@shared/types'

/**
 * The screen for choosing a practice video and starting an analysis.
 *
 * The video is checked as soon as it is chosen rather than when the button is pressed. A
 * full analysis takes minutes, and being told at the end of one that the file was never
 * suitable is the most frustrating possible way to find out. The check itself takes a couple
 * of seconds, so the answer arrives while the user is still looking at the screen.
 *
 * A file that fails cannot be analysed from here, and the reason is shown in place of a
 * general error. A file that passes but has something worth mentioning, such as the fact
 * that only one person is ever analysed, is accepted with those notes shown alongside it.
 *
 * Drag and drop is still to be added.
 */
export default function Upload(): JSX.Element {
  const [videoPath, setVideoPath] = useState<string | null>(null)
  const [fusionMode, setFusionMode] = useState<FusionMode>('adaptive')
  const [checking, setChecking] = useState(false)
  const [preparing, setPreparing] = useState(false)
  const [check, setCheck] = useState<VideoValidation | null>(null)
  const [error, setError] = useState<string | null>(null)
  const navigate = useNavigate()

  const pick = async (): Promise<void> => {
    const path = await window.bodytalk.openVideoDialog()
    if (!path) return
    setVideoPath(path)
    setError(null)
    setCheck(null)
    setChecking(true)
    try {
      setCheck(await window.bodytalk.validateVideo(path))
    } finally {
      // Whatever happened, the spinner has to stop. Leaving it running would strand the
      // user on a screen where nothing works and nothing explains why.
      setChecking(false)
    }
  }

  const start = async (): Promise<void> => {
    if (!videoPath) return
    // Starting a session copies the video into it, which on a long recording takes a moment.
    // Saying so is better than a button that looks like it was not pressed.
    setPreparing(true)
    let res: { sessionId?: number; error?: string }
    try {
      res = await window.bodytalk.createSession({ videoPath, fusionMode })
    } finally {
      setPreparing(false)
    }
    if (res.error || !res.sessionId) {
      setError(res.error ?? 'Could not create session.')
      return
    }
    navigate(`/processing/${res.sessionId}`, {
      state: { videoPath, fusionMode, selfTest: false }
    })
  }

  const rejected = check !== null && !check.ok
  const canAnalyse = Boolean(videoPath) && !checking && !preparing && !rejected

  const lengthSummary =
    check?.durationS && check.durationS > 0
      ? `${Math.round(check.durationS)} seconds${check.width ? `, ${check.width}×${check.height}` : ''}`
      : null

  return (
    <div>
      <a className="back" onClick={() => navigate('/')}>
        ← Back
      </a>
      <h1 style={{ marginTop: 12 }}>New analysis</h1>
      <p className="subtitle">
        Select a practice interview video. It stays on this computer and is never uploaded anywhere.
      </p>
      <p className="label" style={{ marginTop: -8, marginBottom: 16 }}>
        One person in frame · 1 to 10 minutes · MP4 or WebM recordings work best
      </p>

      <div className="card" style={{ marginBottom: 16 }}>
        <button onClick={pick}>Choose video…</button>
        <div className="label" style={{ marginTop: 10 }}>
          {videoPath ?? 'No file selected'}
        </div>

        {checking && (
          <div className="label" style={{ marginTop: 8 }}>
            Checking the video…
          </div>
        )}

        {rejected && (
          <div style={{ marginTop: 10, color: '#ff8b8b' }}>
            {check?.reason ?? 'This video cannot be analysed.'}
          </div>
        )}

        {check?.ok && lengthSummary && (
          <div className="label" style={{ marginTop: 8 }}>
            Ready to analyse. {lengthSummary}.
          </div>
        )}

        {check?.ok &&
          check.warnings?.map((note) => (
            <div key={note} className="label" style={{ marginTop: 6, opacity: 0.75 }}>
              {note}
            </div>
          ))}
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

      <button className="primary" disabled={!canAnalyse} onClick={start}>
        {checking ? 'Checking…' : preparing ? 'Preparing…' : 'Analyse'}
      </button>
    </div>
  )
}
