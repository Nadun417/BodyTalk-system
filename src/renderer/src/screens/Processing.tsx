import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams, useLocation } from 'react-router-dom'
import type { FusionMode, ProgressUpdate } from '@shared/types'
import { clock } from '../lib/format'

interface ProcessingState {
  selfTest?: boolean
  fusionMode?: FusionMode
  videoPath?: string
}

/**
 * The stages the analysis moves through, in the order they happen.
 *
 * The pipeline announces which stage it is in by a short name of its own. Those names are for
 * the two programs to agree on, not for anybody to read, so they are turned into a sentence
 * here. Showing the stages as a row of segments also answers the question a single bar cannot:
 * not just how far through the current piece of work it is, but how much work there is
 * altogether. Detection is by far the longest of them, which is worth being able to see.
 */
const STAGES = [
  { key: 'extracting', title: 'Reading the video' },
  { key: 'detecting', title: 'Detecting landmarks' },
  { key: 'analysing', title: 'Measuring each channel' },
  { key: 'fusing', title: 'Combining the channels' },
  { key: 'feedback', title: 'Writing your feedback' }
]

/**
 * The screen shown while a video is being analysed.
 *
 * The progress shown is the real count of frames processed, not an animation running on a
 * timer. Analysis can take several minutes, and a bar that is honestly slow is easier to wait
 * through than one that races to ninety percent and then stops. Cancelling actually stops the
 * work rather than just hiding it.
 */
export default function Processing(): JSX.Element {
  const { id } = useParams()
  const sessionId = Number(id)
  const navigate = useNavigate()
  const state = (useLocation().state ?? {}) as ProcessingState
  const [progress, setProgress] = useState<ProgressUpdate | null>(null)
  const [elapsed, setElapsed] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const started = useRef(false)

  useEffect(() => {
    const tick = setInterval(() => setElapsed((s) => s + 1), 1000)
    return () => clearInterval(tick)
  }, [])

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
        .then((outcome) => {
          // Three endings, told apart by what came back rather than by reading an error
          // message. Messages do not survive the trip from the backend unchanged, so a
          // cancelled run used to be mistaken for a failure and the user was left here
          // watching a progress bar that had stopped.
          if (outcome.cancelled) navigate('/', { replace: true })
          else if (outcome.error) setError(outcome.error)
          else navigate(`/dashboard/${sessionId}`, { replace: true })
        })
        .catch((e: Error) => setError(e.message))
    }

    return unsubscribe
  }, [sessionId])

  const stageIndex = Math.max(
    0,
    STAGES.findIndex((s) => s.key === progress?.stage)
  )
  const stage = STAGES[stageIndex]
  const pct =
    progress && progress.total > 0 ? Math.round((progress.done / progress.total) * 100) : 0

  if (error) {
    return (
      <main className="page narrow center" style={{ paddingTop: 80 }}>
        <h1>The analysis could not finish</h1>
        <p className="subtitle" style={{ marginBottom: 20 }}>
          Nothing was saved for this session.
        </p>
        <div className="notice bad" style={{ textAlign: 'left' }}>
          {error}
        </div>
        <button className="primary" style={{ marginTop: 20 }} onClick={() => navigate('/')}>
          Back to your sessions
        </button>
      </main>
    )
  }

  return (
    <main className="page narrow center" style={{ paddingTop: 72 }}>
      <div className="step-ring">
        {progress ? stageIndex + 1 : '·'}/{STAGES.length}
      </div>

      <h1>Analysing your video…</h1>
      <p style={{ fontWeight: 650, margin: '14px 0 2px' }}>
        {progress ? stage.title : 'Starting the analysis'}
      </p>
      <p className="subtitle">
        {progress
          ? `Step ${stageIndex + 1} of ${STAGES.length}`
          : 'This runs entirely on your device'}
      </p>

      <div className="segments">
        {STAGES.map((s, i) => (
          <span
            key={s.key}
            className={`segment ${i < stageIndex ? 'done' : i === stageIndex && progress ? 'active' : ''}`}
          />
        ))}
      </div>

      <div className="bar">
        <i style={{ width: `${pct}%` }} />
      </div>

      <div className="between" style={{ marginTop: 8, alignItems: 'center' }}>
        <strong>{pct}%</strong>
        <span className="time">
          {progress ? `frame ${progress.done} / ${progress.total}` : 'preparing…'}
        </span>
      </div>

      <p className="subtitle" style={{ marginTop: 18 }}>
        Elapsed {clock(elapsed)} · This runs entirely on your device.
      </p>

      <button style={{ marginTop: 14 }} onClick={() => window.bodytalk.cancelAnalysis(sessionId)}>
        Cancel
      </button>
    </main>
  )
}
