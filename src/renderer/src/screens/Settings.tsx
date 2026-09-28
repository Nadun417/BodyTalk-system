import { useEffect, useState } from 'react'
import type { AppSettings } from '@shared/types'
import {
  ANALYSIS_FPS_WARNING,
  DEFAULT_SETTINGS,
  SETTING_RANGES,
  SHORT_VIDEO_WARNING,
  clampSetting
} from '@shared/settings'

/**
 * The screen for the two numbers the analysis is allowed to be told about.
 *
 * Both were meant to be the user's to set from the start, and both were reachable only by
 * editing the database until this screen existed. They are shown together with what changing
 * them costs, because neither is a free choice: a shorter minimum lets in recordings the rules
 * cannot say much about, and a different frame rate changes what a second of analysis is made
 * of. Saying so next to the input is the only place a warning of that kind is any use.
 *
 * Nothing is saved as it is typed. A half-finished number on the way to another one, 1 on the
 * way to 120, is a setting the app would otherwise adopt for as long as it took to type the
 * rest, and the analysis reads these the moment a video is chosen.
 */
export default function Settings(): JSX.Element {
  const [saved, setSaved] = useState<AppSettings | null>(null)
  const [minDurationS, setMinDurationS] = useState('')
  const [analysisFps, setAnalysisFps] = useState('')
  const [note, setNote] = useState<string | null>(null)

  const load = (settings: AppSettings): void => {
    setSaved(settings)
    setMinDurationS(String(settings.minDurationS))
    setAnalysisFps(String(settings.analysisFps))
  }

  useEffect(() => {
    window.bodytalk.getSettings().then(load)
  }, [])

  if (!saved) return <main className="page narrow" />

  // What would actually be stored if this were saved now, which is what the screen shows back
  // after saving. The backend puts anything out of range back inside it, so the screen works
  // the same out rather than letting the two disagree about what was just saved.
  const wanted = {
    minDurationS: clampSetting('minDurationS', minDurationS),
    analysisFps: clampSetting('analysisFps', analysisFps)
  }
  const changed =
    wanted.minDurationS !== saved.minDurationS || wanted.analysisFps !== saved.analysisFps

  const save = async (patch: Partial<AppSettings>, message: string): Promise<void> => {
    load(await window.bodytalk.setSettings(patch))
    setNote(message)
  }

  return (
    <main className="page narrow">
      <div className="center" style={{ margin: '18px 0 24px' }}>
        <h1>Settings</h1>
        <p className="subtitle">
          These apply to the next video you analyse. Sessions already analysed keep the settings
          they were analysed with.
        </p>
      </div>

      <div className="card">
        <label className="field" htmlFor="min-duration">
          <span className="field-label">Shortest video accepted</span>
          <span className="field-note">
            A video shorter than this is refused before it is analysed. Between{' '}
            {SETTING_RANGES.minDurationS.min} and {SETTING_RANGES.minDurationS.max} seconds.
            Normally {DEFAULT_SETTINGS.minDurationS}.
          </span>
          <span className="field-input">
            <input
              id="min-duration"
              type="number"
              min={SETTING_RANGES.minDurationS.min}
              max={SETTING_RANGES.minDurationS.max}
              step={SETTING_RANGES.minDurationS.step}
              value={minDurationS}
              onChange={(e) => {
                setMinDurationS(e.target.value)
                setNote(null)
              }}
            />
            <span className="unit">seconds</span>
          </span>
        </label>
        <div className="notice warn" style={{ marginBottom: 0 }}>
          {SHORT_VIDEO_WARNING}
        </div>
      </div>

      <div className="card">
        <label className="field" htmlFor="analysis-fps">
          <span className="field-label">Frames analysed each second</span>
          <span className="field-note">
            How many frames of each second the analysis looks at. Between{' '}
            {SETTING_RANGES.analysisFps.min} and {SETTING_RANGES.analysisFps.max}. Normally{' '}
            {DEFAULT_SETTINGS.analysisFps}.
          </span>
          <span className="field-input">
            <input
              id="analysis-fps"
              type="number"
              min={SETTING_RANGES.analysisFps.min}
              max={SETTING_RANGES.analysisFps.max}
              step={SETTING_RANGES.analysisFps.step}
              value={analysisFps}
              onChange={(e) => {
                setAnalysisFps(e.target.value)
                setNote(null)
              }}
            />
            <span className="unit">frames a second</span>
          </span>
        </label>
        <div className="notice warn" style={{ marginBottom: 0 }}>
          {ANALYSIS_FPS_WARNING}
        </div>
      </div>

      <div className="card">
        <span className="field-label">Where reports are saved</span>
        <p className="field-note" style={{ marginBottom: 10 }}>
          The save box opens here next time. It is set by saving a report, not here.
        </p>
        <div className="path-row">
          <span className="path">{saved.reportSavePath ?? 'Not set yet'}</span>
          {saved.reportSavePath && (
            <button className="soft" onClick={() => save({ reportSavePath: null }, 'Forgotten.')}>
              Forget it
            </button>
          )}
        </div>
      </div>

      <div className="row" style={{ marginTop: 16 }}>
        <button
          className="primary"
          disabled={!changed}
          onClick={() => save(wanted, 'Saved. The next analysis will use these.')}
        >
          Save changes
        </button>
        <button
          className="soft"
          onClick={() =>
            save(
              {
                minDurationS: DEFAULT_SETTINGS.minDurationS,
                analysisFps: DEFAULT_SETTINGS.analysisFps
              },
              'Put back to the normal settings.'
            )
          }
        >
          Use the normal settings
        </button>
      </div>

      {note && (
        <div className="notice ok" style={{ marginTop: 14 }}>
          {note}
        </div>
      )}
      {changed && (
        <p className="muted" style={{ marginTop: 12, fontSize: 13 }}>
          Not saved yet. This would be kept as {wanted.minDurationS} seconds and{' '}
          {wanted.analysisFps} frames a second.
        </p>
      )}
    </main>
  )
}
