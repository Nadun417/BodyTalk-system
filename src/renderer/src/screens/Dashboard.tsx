import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import type { AnalysisEvent, ScoredChannel, Channel } from '@shared/types'
import type { SessionDetail } from '../../../preload/index'
import ScoresOverTimeChart from '../components/charts/ScoresOverTimeChart'
import WeightOverTimeChart from '../components/charts/WeightOverTimeChart'
import { clock, shortDate, CHANNEL_COLOUR, CHANNEL_NAME } from '../lib/format'

/**
 * The results screen.
 *
 * It is arranged as an argument rather than as a pile of charts. The scores say what happened;
 * the video and its list of moments let the user check that for themselves; the two charts
 * show how the scores moved and how much each channel counted while they did; the findings say
 * what was noticed and when; and the advice at the end says what to do about it.
 *
 * Being able to jump to a moment is the part that makes the rest trustworthy. A score on its
 * own asks to be believed. A score next to the few seconds of video it came from can be
 * checked, and someone who disagrees with a finding can see exactly what the analysis was
 * looking at when it made it.
 */
export default function Dashboard(): JSX.Element {
  const { id } = useParams()
  const sessionId = Number(id)
  const navigate = useNavigate()
  const [detail, setDetail] = useState<SessionDetail | null>(null)
  const [videoUrl, setVideoUrl] = useState<string | null>(null)

  useEffect(() => {
    window.bodytalk.getSession(sessionId).then(setDetail)
    window.bodytalk.videoUrl(sessionId).then(setVideoUrl)
  }, [sessionId])

  if (!detail) return <main className="page" />

  const { session, windows, events, recommendations } = detail
  const channels: ScoredChannel[] = ['face', 'pose', 'hands']
  const windowCount = new Set(windows.map((w) => w.tStartS)).size

  return (
    <main className="page">
      <div className="between" style={{ marginBottom: 18 }}>
        <div>
          <h1 style={{ fontSize: 22, marginBottom: 4 }}>
            Session {shortDate(session.createdAt)}
            {session.videoDurationS > 0 && ` · ${clock(session.videoDurationS)}`}{' '}
            <span className={`badge ${session.fusionMode}`} style={{ verticalAlign: 'middle' }}>
              {session.fusionMode === 'adaptive' ? 'Adaptive' : 'Fixed'}
            </span>
          </h1>
          <p className="subtitle">
            {session.videoFilename} · {windowCount} seconds analysed
          </p>
        </div>
        <div className="row">
          <button onClick={() => navigate('/')}>Sessions</button>
          <button className="primary" onClick={() => navigate(`/report/${sessionId}`)}>
            Export PDF
          </button>
        </div>
      </div>

      <div className="scores">
        <ScoreCard label="Overall" score={session.overallScore} channel="fused" lead />
        {channels.map((c) => (
          <ScoreCard key={c} label={CHANNEL_NAME[c]} score={session.channelScores[c]} channel={c} />
        ))}
      </div>

      {session.overallSummary && (
        <div className="card">
          <p style={{ margin: 0, fontSize: 15, lineHeight: 1.55 }}>{session.overallSummary}</p>
        </div>
      )}

      <SeeTheMoment videoUrl={videoUrl} events={events} durationS={session.videoDurationS} />

      <div className="card">
        <p className="card-title">Scores over time</p>
        <p className="card-note">
          The overall line is made from the three beneath it, weighted second by second.
        </p>
        <ScoresOverTimeChart windows={windows} />
      </div>

      <div className="card">
        <p className="card-title">How much each signal counted</p>
        <p className="card-note">
          The three shares always add up to the whole.{' '}
          {session.fusionMode === 'adaptive'
            ? 'When a channel cannot be seen clearly its share shrinks and the others take over.'
            : 'Fixed weighting keeps the shares equal between whatever the camera could see.'}
        </p>
        <WeightOverTimeChart windows={windows} fusionMode={session.fusionMode} />
      </div>

      <div className="card">
        <p className="card-title">What we noticed</p>
        <p className="card-note">Each of these describes something visible in the video.</p>
        {events.length === 0 ? (
          <div className="empty">Nothing stood out for long enough to report.</div>
        ) : (
          events.map((e, i) => <Finding key={i} event={e} />)
        )}
      </div>

      {recommendations.length > 0 && (
        <div className="card">
          <p className="card-title">What to try next</p>
          <p className="card-note">
            Ranked by what would make the most difference in your next take.
          </p>
          {recommendations.map((r) => (
            <div className="advice" key={r.rank}>
              <span className="rank">{r.rank}</span>
              <div>
                <div className="row" style={{ marginBottom: 3 }}>
                  <strong>{r.title}</strong>
                  {r.channel !== 'fused' && (
                    <span className={`badge ${r.channel}`}>{CHANNEL_NAME[r.channel]}</span>
                  )}
                  {r.kind === 'maintain' && <span className="badge plain">Keep it up</span>}
                </div>
                <div className="muted">{r.body}</div>
              </div>
            </div>
          ))}
        </div>
      )}
    </main>
  )
}

function ScoreCard({
  label,
  score,
  channel,
  lead
}: {
  label: string
  score: number | null
  channel: Channel
  lead?: boolean
}): JSX.Element {
  return (
    <div className={`score-card ${lead ? 'lead' : ''}`}>
      <div className="between" style={{ alignItems: 'center' }}>
        <span className="label">{label}</span>
        <span className="dot" style={{ background: CHANNEL_COLOUR[channel] }} />
      </div>
      <div className="n" style={{ color: CHANNEL_COLOUR[channel] }}>
        {score ?? '—'}
      </div>
      <div className="meter">
        <i style={{ width: `${score ?? 0}%`, background: CHANNEL_COLOUR[channel] }} />
      </div>
    </div>
  )
}

/**
 * The video, and the list of moments that jump to a place in it.
 *
 * The marks on the bar under the video are the same moments as the list beside it, in the
 * colour of the channel each came from, so the shape of the session is visible on the timeline
 * itself before a word of it is read.
 */
function SeeTheMoment({
  videoUrl,
  events,
  durationS
}: {
  videoUrl: string | null
  events: AnalysisEvent[]
  durationS: number
}): JSX.Element {
  const video = useRef<HTMLVideoElement>(null)
  const [at, setAt] = useState(0)
  const [length, setLength] = useState(durationS)
  const [playing, setPlaying] = useState(false)
  const [current, setCurrent] = useState<number | null>(null)

  const jumpTo = (seconds: number, index: number | null): void => {
    const el = video.current
    if (!el) return
    el.currentTime = seconds
    setAt(seconds)
    setCurrent(index)
  }

  const toggle = (): void => {
    const el = video.current
    if (!el) return
    if (el.paused) void el.play().catch(() => setPlaying(false))
    else el.pause()
  }

  const total = length || durationS || 1

  return (
    <div className="card">
      <p className="card-title">See the moment</p>
      <p className="card-note">
        Pick any moment below to jump straight to it, and judge the finding for yourself.
      </p>

      <div className="moment-grid">
        <div>
          <div className="player">
            {videoUrl ? (
              <video
                ref={video}
                src={videoUrl}
                onLoadedMetadata={(e) => setLength(e.currentTarget.duration)}
                onTimeUpdate={(e) => setAt(e.currentTarget.currentTime)}
                onPlay={() => setPlaying(true)}
                onPause={() => setPlaying(false)}
                onClick={toggle}
              />
            ) : (
              <p className="missing">
                This session has no saved copy of its video, so there is nothing to play here.
                Sessions analysed from now on keep their own copy.
              </p>
            )}
          </div>

          <div className="scrubber">
            <div className="played" style={{ width: `${(100 * at) / total}%` }} />
            <div className="marks">
              {events.map((e, i) => (
                <i
                  key={i}
                  style={{
                    left: `${(100 * e.tStartS) / total}%`,
                    background: CHANNEL_COLOUR[e.channel]
                  }}
                />
              ))}
            </div>
            <input
              type="range"
              min={0}
              max={Math.round(total)}
              step={1}
              value={Math.round(at)}
              disabled={!videoUrl}
              onChange={(e) => jumpTo(Number(e.target.value), null)}
              aria-label="Move through the video"
            />
          </div>

          <div className="transport">
            <button
              className="round"
              disabled={!videoUrl}
              onClick={() => jumpTo(Math.max(0, at - 5), null)}
              aria-label="Back five seconds"
            >
              ‹
            </button>
            <button
              className="round play"
              disabled={!videoUrl}
              onClick={toggle}
              aria-label="Play or pause"
            >
              {playing ? '❚❚' : '▶'}
            </button>
            <button
              className="round"
              disabled={!videoUrl}
              onClick={() => jumpTo(Math.min(total, at + 5), null)}
              aria-label="Forward five seconds"
            >
              ›
            </button>
            <span className="time">
              {clock(at)} / {clock(total)}
            </span>
          </div>
        </div>

        <div>
          <p className="label" style={{ marginBottom: 8 }}>
            Jump to a moment
          </p>
          {events.length === 0 ? (
            <div className="empty">No moments were flagged in this session.</div>
          ) : (
            events.map((e, i) => (
              <button
                key={i}
                className={`moment ${current === i ? 'current' : ''}`}
                disabled={!videoUrl}
                onClick={() => jumpTo(e.tStartS, i)}
              >
                <span className="stamp">{clock(e.tStartS)}</span>
                <span className="moment-text">{e.message}</span>
                <span className={`badge ${e.channel}`}>{CHANNEL_NAME[e.channel]}</span>
              </button>
            ))
          )}
          {events.length > 0 && (
            <p className="muted" style={{ fontSize: 12, marginTop: 10 }}>
              The marks under the video are these same moments, in each channel&apos;s colour.
            </p>
          )}
        </div>
      </div>
    </div>
  )
}

/**
 * One thing the analysis noticed, marked by how strongly it was flagged.
 *
 * Three marks rather than four, because the point is only whether this is something that went
 * well, something worth attention, or something merely worth knowing. The tick is for the
 * things the analysis records approvingly, which matter: a list made only of faults would read
 * as a telling-off, and people practising for an interview are nervous enough already.
 */
function Finding({ event }: { event: AnalysisEvent }): JSX.Element {
  const tone =
    event.severity === 'info'
      ? 'good'
      : event.severity === 'high' || event.severity === 'medium'
        ? 'warn'
        : 'info'
  const mark = tone === 'good' ? '✓' : tone === 'warn' ? '!' : 'i'
  return (
    <div className={`finding ${tone}`}>
      <span className="finding-mark">{mark}</span>
      <div className="finding-body">
        <div className="row" style={{ marginBottom: 2 }}>
          <span className="stamp">
            {clock(event.tStartS)} – {clock(event.tEndS)}
          </span>
          <span className={`badge ${event.channel}`}>{CHANNEL_NAME[event.channel]}</span>
        </div>
        <div>{event.message}</div>
        {event.suggestion && (
          <div className="muted" style={{ marginTop: 3 }}>
            {event.suggestion}
          </div>
        )}
      </div>
    </div>
  )
}
