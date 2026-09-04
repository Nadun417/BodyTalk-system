import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import type { FusionMode, VideoValidation } from '@shared/types'
import { clock } from '../lib/format'

/**
 * The screen for choosing a practice video and starting an analysis.
 *
 * The video is checked as soon as it is chosen rather than when the button is pressed. A full
 * analysis takes minutes, and being told at the end of one that the file was never suitable
 * is the most frustrating possible way to find out. The check itself takes a couple of
 * seconds, so the answer arrives while the user is still looking at the screen.
 *
 * A file can be dropped onto the panel or picked with the button. Dropping is how most people
 * expect to hand a file to a desktop application, and the file picker stays because it is the
 * only way that works with the keyboard alone.
 */
export default function Upload(): JSX.Element {
  const [videoPath, setVideoPath] = useState<string | null>(null)
  const [fusionMode, setFusionMode] = useState<FusionMode>('adaptive')
  const [checking, setChecking] = useState(false)
  const [preparing, setPreparing] = useState(false)
  const [check, setCheck] = useState<VideoValidation | null>(null)
  const [over, setOver] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const navigate = useNavigate()

  const choose = async (path: string): Promise<void> => {
    setVideoPath(path)
    setError(null)
    setCheck(null)
    setChecking(true)
    try {
      setCheck(await window.bodytalk.validateVideo(path))
    } finally {
      // Whatever happened, the spinner has to stop. Leaving it running would strand the user
      // on a screen where nothing works and nothing explains why.
      setChecking(false)
    }
  }

  const browse = async (): Promise<void> => {
    const path = await window.bodytalk.openVideoDialog()
    if (path) await choose(path)
  }

  /**
   * Take a file that was dragged onto the panel.
   *
   * Electron hands the real location of a dropped file over on the file object, which is what
   * the check and the analysis need: everything downstream works with a path on this machine,
   * not with the file's contents. Anything dropped that is not a file, a folder for instance,
   * simply has no path and is ignored rather than reported as an error.
   */
  const drop = async (event: React.DragEvent): Promise<void> => {
    event.preventDefault()
    setOver(false)
    const file = event.dataTransfer.files[0]
    const path = file ? window.bodytalk.pathForFile(file) : ''
    if (path) await choose(path)
    else if (file) setError('That does not look like a video file saved on this computer.')
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
  const filename = videoPath?.split(/[\\/]/).pop()

  return (
    <main className="page narrow">
      <div className="center" style={{ margin: '18px 0 24px' }}>
        <h1>Analyse a practice interview video</h1>
        <p className="subtitle">Everything runs on your device and nothing is uploaded.</p>
      </div>

      <div
        className={`dropzone ${over ? 'over' : ''}`}
        onDragOver={(e) => {
          e.preventDefault()
          setOver(true)
        }}
        onDragLeave={() => setOver(false)}
        onDrop={drop}
      >
        <div className="dropzone-icon">↑</div>
        <div className="row" style={{ justifyContent: 'center' }}>
          <span>Drag a video here, or</span>
          <button className="soft" onClick={browse}>
            Browse files
          </button>
        </div>
        <p className="muted" style={{ marginBottom: 0, marginTop: 12, fontSize: 13 }}>
          MP4 or WebM · 1–10 minutes · one person in frame
        </p>
        {filename && (
          <p style={{ marginBottom: 0, marginTop: 14, fontWeight: 600 }}>
            {filename}
            {checking && (
              <span className="muted" style={{ fontWeight: 400 }}>
                {' '}
                · checking…
              </span>
            )}
          </p>
        )}
      </div>

      {check?.ok && !checking && (
        <div className="notice ok">
          Ready to analyse
          {check.durationS ? ` · ${clock(check.durationS)}` : ''}
          {check.width ? ` · ${check.width}×${check.height}` : ''}
        </div>
      )}
      {rejected && (
        <div className="notice bad">{check?.reason ?? 'This video cannot be analysed.'}</div>
      )}
      {check?.warnings?.map((note) => (
        <div className="notice warn" key={note}>
          {note}
        </div>
      ))}
      {error && <div className="notice bad">{error}</div>}

      <h2 style={{ margin: '26px 0 10px' }}>Fusion mode</h2>

      <Choice
        selected={fusionMode === 'adaptive'}
        onSelect={() => setFusionMode('adaptive')}
        title="Adaptive"
        note="Weights adjust to what the camera can actually see."
        tag="Recommended"
      />
      <Choice
        selected={fusionMode === 'fixed'}
        onSelect={() => setFusionMode('fixed')}
        title="Fixed"
        note="Equal weighting, used for evaluation."
      />

      <button
        className="primary block"
        style={{ marginTop: 16 }}
        disabled={!canAnalyse}
        onClick={start}
      >
        {checking ? 'Checking…' : preparing ? 'Preparing…' : 'Start analysis'}
      </button>

      {!videoPath && (
        <p className="muted center" style={{ marginTop: 12, fontSize: 13 }}>
          Choose a video to begin.
        </p>
      )}
    </main>
  )
}

function Choice({
  selected,
  onSelect,
  title,
  note,
  tag
}: {
  selected: boolean
  onSelect: () => void
  title: string
  note: string
  tag?: string
}): JSX.Element {
  return (
    <button
      className={`choice ${selected ? 'selected' : ''}`}
      onClick={onSelect}
      aria-pressed={selected}
    >
      <span className="choice-dot" />
      <span style={{ flex: 1 }}>
        <span style={{ display: 'block', fontWeight: 650, color: 'var(--text)' }}>{title}</span>
        <span style={{ display: 'block', color: 'var(--muted)', fontWeight: 400 }}>{note}</span>
      </span>
      {tag && <span className="badge plain">{tag}</span>}
    </button>
  )
}
