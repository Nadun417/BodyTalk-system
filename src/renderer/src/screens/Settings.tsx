import { useCallback, useEffect, useState, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import type { AppSettings } from '@shared/types'
import {
  ANALYSIS_FPS_WARNING,
  DEFAULT_SETTINGS,
  SHORT_VIDEO_WARNING,
  settingChoices
} from '@shared/settings'
import { ArrowLeftIcon, CheckIcon, ChevronDownIcon } from '../components/Icons'

/**
 * The settings screen.
 *
 * Rebuilt after the first version was found hard to use by the person it was for. That version
 * had no way back to the screen it was opened from, two orange warnings that were always on
 * show whether or not they applied, typed-in number boxes that could hold impossible values, and
 * a Save button that was easy to forget before leaving. So now:
 *
 * - "Back" returns to wherever the screen was opened from, and Escape does the same.
 * - Each setting is a list to pick from, so an impossible value cannot be entered, and a change
 *   is saved the moment it is made, with "Saved" shown beside it. With nothing typed, there is no
 *   half-finished number to worry about saving, which is why the first version had a button.
 * - A warning appears only when it applies: the one about short videos when the setting is below
 *   the recommended length, and the one about pictures per second when it is not 6.
 * - How many pictures are checked each second sits under "Advanced settings", closed, because
 *   almost nobody should change it. It opens by itself if it has been changed, so a setting that
 *   is not the recommended one is never hidden.
 */
export default function Settings(): JSX.Element {
  const navigate = useNavigate()
  const [saved, setSaved] = useState<AppSettings | null>(null)
  const [status, setStatus] = useState<{ key: string; text: string } | null>(null)
  const [advancedOpen, setAdvancedOpen] = useState(false)

  useEffect(() => {
    window.bodytalk.getSettings().then((s) => {
      setSaved(s)
      if (s.analysisFps !== DEFAULT_SETTINGS.analysisFps) setAdvancedOpen(true)
    })
  }, [])

  // Back to wherever the screen was opened from. If it was the first screen shown, there is
  // nowhere to go back to, so it goes to the list of sessions instead.
  const goBack = useCallback((): void => {
    const position = (window.history.state as { idx?: number } | null)?.idx ?? 0
    if (position > 0) navigate(-1)
    else navigate('/')
  }, [navigate])

  useEffect(() => {
    const onKey = (e: KeyboardEvent): void => {
      if (e.key === 'Escape') goBack()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [goBack])

  if (!saved) return <main className="page narrow" />

  const save = async (key: string, patch: Partial<AppSettings>, text: string): Promise<void> => {
    setSaved(await window.bodytalk.setSettings(patch))
    setStatus({ key, text })
  }

  const onRecommended =
    saved.minDurationS === DEFAULT_SETTINGS.minDurationS &&
    saved.analysisFps === DEFAULT_SETTINGS.analysisFps

  return (
    <main className="page narrow settings">
      <button type="button" className="ghost back-button" onClick={goBack} title="Go back (Esc)">
        <ArrowLeftIcon />
        Back
      </button>

      <header className="settings-head">
        <h1>Settings</h1>
        <p className="subtitle">
          Changes save straight away and apply to the next video you analyse. Videos you have
          already analysed keep their results.
        </p>
      </header>

      <section className="card settings-section" aria-labelledby="videos-heading">
        <h2 id="videos-heading">Videos</h2>
        <Choice
          id="min-duration"
          label="Shortest video"
          help="Videos shorter than this cannot be analysed."
          value={saved.minDurationS}
          choices={settingChoices('minDurationS', saved.minDurationS)}
          recommended={DEFAULT_SETTINGS.minDurationS}
          describe={(n) => `${n} seconds`}
          status={status?.key === 'minDurationS' ? status.text : null}
          onChange={(n) => save('minDurationS', { minDurationS: n }, 'Saved')}
        >
          {saved.minDurationS < DEFAULT_SETTINGS.minDurationS && (
            <p className="notice warn setting-notice">{SHORT_VIDEO_WARNING}</p>
          )}
        </Choice>
      </section>

      <section className="card settings-section" aria-labelledby="reports-heading">
        <h2 id="reports-heading">Reports</h2>
        <div className="setting">
          <span className="setting-label">Folder for saved reports</span>
          <p className="setting-help">
            When you save a report as a PDF, BodyTalk opens this folder first. It remembers the last
            folder you used.
          </p>
          {saved.reportSavePath ? (
            <div className="path-row">
              <span className="path">{saved.reportSavePath}</span>
              <button
                type="button"
                className="soft"
                onClick={() => save('reportSavePath', { reportSavePath: null }, 'Cleared')}
              >
                Clear
              </button>
            </div>
          ) : (
            <p className="setting-empty">
              None yet. You will choose one the first time you save a report.
            </p>
          )}
          <Saved text={status?.key === 'reportSavePath' ? status.text : null} />
        </div>
      </section>

      <section className="settings-section advanced">
        <button
          type="button"
          className="disclosure"
          aria-expanded={advancedOpen}
          aria-controls="advanced-settings"
          onClick={() => setAdvancedOpen(!advancedOpen)}
        >
          <ChevronDownIcon className="disclosure-arrow" />
          <span>
            <strong>Advanced settings</strong>
            <span className="muted"> · most people never need to change these</span>
          </span>
        </button>
        {advancedOpen && (
          <div id="advanced-settings" className="card disclosure-body">
            <Choice
              id="analysis-fps"
              label="Pictures checked each second"
              help="BodyTalk studies your video as a series of still pictures. This is how many it takes from each second of video."
              value={saved.analysisFps}
              choices={settingChoices('analysisFps', saved.analysisFps)}
              recommended={DEFAULT_SETTINGS.analysisFps}
              describe={(n) => `${n} a second`}
              status={status?.key === 'analysisFps' ? status.text : null}
              onChange={(n) => save('analysisFps', { analysisFps: n }, 'Saved')}
            >
              {saved.analysisFps !== DEFAULT_SETTINGS.analysisFps && (
                <p className="notice warn setting-notice">{ANALYSIS_FPS_WARNING}</p>
              )}
            </Choice>
          </div>
        )}
      </section>

      <div className="settings-foot">
        <button
          type="button"
          disabled={onRecommended}
          onClick={() =>
            save(
              'reset',
              {
                minDurationS: DEFAULT_SETTINGS.minDurationS,
                analysisFps: DEFAULT_SETTINGS.analysisFps
              },
              'Back to the recommended settings'
            )
          }
        >
          Reset to recommended settings
        </button>
        <Saved text={status?.key === 'reset' ? status.text : null} />
      </div>
    </main>
  )
}

/**
 * One setting chosen from a list: its name, what it does, the list, and a note once it is saved.
 *
 * The recommended value is marked in the list itself, so nobody has to remember what the normal
 * setting was in order to go back to it.
 */
function Choice({
  id,
  label,
  help,
  value,
  choices,
  recommended,
  describe,
  status,
  onChange,
  children
}: {
  id: string
  label: string
  help: string
  value: number
  choices: number[]
  recommended: number
  describe: (n: number) => string
  status: string | null
  onChange: (n: number) => void
  children?: ReactNode
}): JSX.Element {
  return (
    <div className="setting">
      <label className="setting-label" htmlFor={id}>
        {label}
      </label>
      <p className="setting-help" id={`${id}-help`}>
        {help}
      </p>
      <div className="setting-control">
        <span className="select-wrap">
          <select
            id={id}
            value={value}
            aria-describedby={`${id}-help`}
            onChange={(e) => onChange(Number(e.target.value))}
          >
            {choices.map((n) => (
              <option key={n} value={n}>
                {describe(n)}
                {n === recommended ? ' (recommended)' : ''}
              </option>
            ))}
          </select>
          <ChevronDownIcon className="select-arrow" />
        </span>
        <Saved text={status} />
      </div>
      {children}
    </div>
  )
}

/**
 * The note shown beside a setting once it has been saved, read out by screen readers too.
 *
 * The slot is always there and only its words come and go. A screen reader announces a change
 * to a status area it already knows about; one that appears out of nowhere is often missed.
 */
function Saved({ text }: { text: string | null }): JSX.Element {
  return (
    <span className="saved-note" role="status">
      {text && (
        <>
          <CheckIcon />
          {text}
        </>
      )}
    </span>
  )
}
