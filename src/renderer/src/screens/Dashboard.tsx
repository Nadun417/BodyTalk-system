import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import type {
  AnalysisEvent,
  ChannelMetric,
  ChannelCoverage,
  Recommendation,
  ScoredChannel,
  Channel
} from '@shared/types'
import type { SessionDetail } from '../../../preload/index'
import ScoresOverTimeChart from '../components/charts/ScoresOverTimeChart'
import WeightOverTimeChart from '../components/charts/WeightOverTimeChart'
import {
  band,
  clock,
  shortDate,
  shownScore,
  thinNote,
  wholeScore,
  BAND_WORD,
  CHANNEL_COLOUR,
  CHANNEL_NAME,
  SCORE_LEGEND
} from '../lib/format'
import { groupFindings, howOften, type FindingGroup } from '../lib/findings'
import { ChevronDownIcon } from '../components/Icons'

/**
 * The results screen.
 *
 * It is laid out in the order somebody reads it, which is not the order it was built in. The
 * first version opened with four numbers and a dense table of more numbers, put two technical
 * charts in the middle, listed every finding twice, and left what to do about any of it until
 * the very bottom. The person it was for found it hard to read, and they were right.
 *
 * So now: a plain sentence saying how it went; the four scores, each with a word saying what
 * the number means; what to try next; then what was noticed, grouped, beside the video so any
 * of it can be checked; and last, closed until asked for, how the scores were worked out.
 *
 * Being able to jump to a moment is still the part that makes the rest trustworthy. A score on
 * its own asks to be believed. A finding next to the few seconds of video it came from can be
 * checked, and someone who disagrees with it can see exactly what the analysis was looking at.
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

  const { session, windows, events, recommendations, channelMetrics } = detail
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

      {session.overallSummary && (
        <div className="card headline">
          <p>{session.overallSummary}</p>
        </div>
      )}

      <div className="scores">
        <ScoreCard label="Overall" score={session.overallScore} channel="fused" lead />
        {channels.map((c) => (
          <ScoreCard
            key={c}
            label={CHANNEL_NAME[c]}
            score={session.channelScores[c]}
            channel={c}
            coverage={session.channelCoverage?.[c]}
          />
        ))}
      </div>
      <p className="legend">{SCORE_LEGEND}</p>

      {recommendations.length > 0 && <Advice recommendations={recommendations} />}

      <Noticed videoUrl={videoUrl} events={events} durationS={session.videoDurationS} />

      <BehindTheScores>
        {channelMetrics.length > 0 && (
          <div className="card">
            <p className="card-title">What made up each score</p>
            <p className="card-note">
              Each score is an average of the measurements under it, so a middling score usually
              means one of them was low rather than all of them.
            </p>
            <div className="breakdown">
              {channels.map((c) => (
                <ChannelBreakdown
                  key={c}
                  channel={c}
                  score={session.channelScores[c]}
                  coverage={session.channelCoverage?.[c]}
                  metrics={channelMetrics.filter((m) => m.channel === c)}
                />
              ))}
            </div>
          </div>
        )}

        <div className="card">
          <p className="card-title">Scores over time</p>
          <p className="card-note">
            The overall line is made from the three beneath it, weighted second by second.
          </p>
          <ScoresOverTimeChart windows={windows} />
        </div>

        <div className="card">
          <p className="card-title">How much each part counted</p>
          <p className="card-note">
            The three shares always add up to the whole.{' '}
            {session.fusionMode === 'adaptive'
              ? "When the camera can't see one part clearly, its share shrinks and the others take over."
              : 'Fixed weighting keeps the shares equal between whatever the camera could see.'}
          </p>
          <WeightOverTimeChart windows={windows} fusionMode={session.fusionMode} />
        </div>
      </BehindTheScores>
    </main>
  )
}

function ScoreCard({
  label,
  score,
  channel,
  lead,
  coverage
}: {
  label: string
  score: number | null
  channel: Channel
  lead?: boolean
  coverage?: ChannelCoverage | null
}): JSX.Element {
  // A score from a few seconds shows a dash and says how little was measured. The card
  // stays, rather than disappearing, so that the part being barely seen is itself visible.
  const note = thinNote(coverage)
  const shown = wholeScore(shownScore(score, coverage))
  const word = BAND_WORD[band(shown)]
  return (
    <div className={`score-card ${lead ? 'lead' : ''}`}>
      <div className="between" style={{ alignItems: 'center' }}>
        <span className="label">{label}</span>
        <span className="dot" style={{ background: CHANNEL_COLOUR[channel] }} />
      </div>
      <div className="n" style={{ color: CHANNEL_COLOUR[channel] }}>
        {shown ?? '—'}
      </div>
      <div className="meter">
        <i style={{ width: `${shown ?? 0}%`, background: CHANNEL_COLOUR[channel] }} />
      </div>
      {word && <div className={`band-word ${band(shown)}`}>{word}</div>}
      {note && <div className="thin-note">{note}</div>}
    </div>
  )
}

/**
 * What to try next, ranked.
 *
 * Moved above the findings, because it is the part somebody can act on and it used to be the
 * last thing on the screen. The line of numbers under each piece of advice is labelled as the
 * breakdown of that part's score. Without the label it sat directly under a heading about one
 * finding and read as though it were about that finding, which it often is not: "Sit tall and
 * straight" can come with a breakdown whose biggest factor is the shoulders.
 */
function Advice({ recommendations }: { recommendations: Recommendation[] }): JSX.Element {
  return (
    <div className="card">
      <p className="card-title">What to try next</p>
      <p className="card-note">In order of what would make the most difference next time.</p>
      {recommendations.map((r) => (
        <div className="advice" key={r.rank}>
          <span className="rank">{r.rank}</span>
          <div>
            <div className="row" style={{ marginBottom: 3 }}>
              <strong>{r.title}</strong>
              {r.channel !== 'fused' && (
                <span className={`badge ${r.channel}`}>{CHANNEL_NAME[r.channel]}</span>
              )}
            </div>
            <div className="muted">{r.body}</div>
            {r.detail && (
              <div className="advice-detail">
                {r.channel !== 'fused' && (
                  <span className="advice-detail-label">
                    Behind your {CHANNEL_NAME[r.channel].toLowerCase()} score:{' '}
                  </span>
                )}
                {r.detail}
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}

/**
 * What was noticed, grouped by kind, beside the video it came from.
 *
 * This replaces two lists that said the same thing: a list of moments beside the video, and a
 * list of findings further down, each carrying every occurrence separately. Here each kind of
 * finding is one line, saying how often and for how long in all, with every occurrence as a
 * time that jumps the video to it, and the tip said once.
 *
 * The marks on the bar under the video are the same moments, in the colour of the part they
 * came from, so the shape of the session is visible on the timeline before a word is read.
 *
 * The frame around the video takes the recording's own shape, tall for a phone held upright
 * and wide for a camera, so that none of the picture is ever cut off to fit.
 */
function Noticed({
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
  const [current, setCurrent] = useState<AnalysisEvent | null>(null)
  // The recording's width divided by its height, once the video has said how big it is. The
  // frame takes this shape so the whole picture fits in it; see the note on `.player` in the
  // stylesheet for why that matters on this screen in particular.
  const [shape, setShape] = useState<number | null>(null)

  const groups = groupFindings(events)

  const measure = (el: HTMLVideoElement): void => {
    setLength(el.duration)
    if (el.videoWidth > 0 && el.videoHeight > 0) setShape(el.videoWidth / el.videoHeight)
  }

  const jumpTo = (seconds: number, moment: AnalysisEvent | null): void => {
    const el = video.current
    if (!el) return
    el.currentTime = seconds
    setAt(seconds)
    setCurrent(moment)
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
      <p className="card-title">What we noticed</p>
      <p className="card-note">
        Each of these is something visible in the video. Pick a time to jump straight to it and see
        for yourself.
      </p>

      <div className="moment-grid">
        <div>
          <div
            className="player"
            style={shape ? ({ '--shape': shape } as CSSProperties) : undefined}
          >
            {videoUrl ? (
              <video
                ref={video}
                src={videoUrl}
                onLoadedMetadata={(e) => measure(e.currentTarget)}
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
          {groups.length === 0 ? (
            <div className="empty">Nothing came up for long enough to flag.</div>
          ) : (
            groups.map((g) => (
              <FindingRow
                key={g.type}
                group={g}
                current={current}
                canJump={Boolean(videoUrl)}
                onJump={(m) => jumpTo(m.tStartS, m)}
              />
            ))
          )}
        </div>
      </div>
    </div>
  )
}

/**
 * One kind of finding, however many times it happened.
 *
 * The mark says which of three things it is. The tick is only for what went well, which in
 * practice means a natural smile. It used to be given to every finding marked as information,
 * so "Your hands couldn't be seen" arrived with an approving tick beside it. The exclamation
 * mark is for something worth working on, and the "i" is for something merely worth knowing.
 */
function FindingRow({
  group,
  current,
  canJump,
  onJump
}: {
  group: FindingGroup
  current: AnalysisEvent | null
  canJump: boolean
  onJump: (moment: AnalysisEvent) => void
}): JSX.Element {
  const tone = group.type === 'smile' ? 'good' : group.severity === 'info' ? 'info' : 'warn'
  const mark = tone === 'good' ? '✓' : tone === 'warn' ? '!' : 'i'
  return (
    <div className={`finding ${tone}`}>
      <span className="finding-mark">{mark}</span>
      <div className="finding-body">
        <div className="row" style={{ marginBottom: 2, flexWrap: 'wrap' }}>
          <strong>{group.name}</strong>
          <span className={`badge ${group.channel}`}>{CHANNEL_NAME[group.channel]}</span>
        </div>
        <div className="muted" style={{ fontSize: 13 }}>
          {howOften(group)}
        </div>
        <div className="times">
          {group.moments.map((m, i) => (
            <button
              key={i}
              className={`time-chip ${current === m ? 'current' : ''}`}
              disabled={!canJump}
              onClick={() => onJump(m)}
              title={m.message}
              aria-label={`Jump to ${clock(m.tStartS)}: ${m.message}`}
            >
              {clock(m.tStartS)}
            </button>
          ))}
        </div>
        {group.tip && <div className="finding-tip">{group.tip}</div>}
      </div>
    </div>
  )
}

/**
 * How the scores were worked out, closed until asked for.
 *
 * Everything in here is true and some of it is the most important material in the project,
 * the chart of how much each part counted in particular. But none of it is what somebody
 * practising for an interview needs first, and open by default it pushed the part they did
 * need further down the screen. Whether it is open is remembered on this machine, so anyone
 * who wants it every time only has to open it once.
 *
 * The charts are only drawn while it is open. Drawn inside a closed section they would be
 * sized to nothing, and would come out squashed when it opened.
 */
function BehindTheScores({ children }: { children: ReactNode }): JSX.Element {
  const [open, setOpen] = useState<boolean>(() => {
    try {
      return localStorage.getItem('dashboard.behind') === 'open'
    } catch {
      return false
    }
  })

  const toggle = (): void => {
    const next = !open
    setOpen(next)
    try {
      localStorage.setItem('dashboard.behind', next ? 'open' : 'closed')
    } catch {
      // Not remembering it costs one click next time, which is not worth interrupting for.
    }
  }

  return (
    <section className="behind">
      <button type="button" className="disclosure" aria-expanded={open} onClick={toggle}>
        <ChevronDownIcon className="disclosure-arrow" />
        <span>
          <strong>Behind the scores</strong>
          <span className="muted">
            {' '}
            · what each score was made of, and how the three parts were weighted
          </span>
        </span>
      </button>
      {open && <div className="behind-body">{children}</div>}
    </section>
  )
}

/**
 * What one part's score was made of.
 *
 * The measurements arrive worst first, which is deliberate: the one at the top is the one
 * that held the part back most, and putting it there means the user does not have to compare
 * three numbers to find it.
 *
 * A measurement that did not count toward the score is shown greyed and labelled rather than
 * hidden. Hiding it would be tidier but less honest, since it was still measured, and showing
 * it like the others would imply it shaped a number it had no part in.
 */
function ChannelBreakdown({
  channel,
  score,
  coverage,
  metrics
}: {
  channel: ScoredChannel
  score: number | null
  coverage?: ChannelCoverage | null
  metrics: ChannelMetric[]
}): JSX.Element {
  const note = thinNote(coverage)
  const shown = wholeScore(shownScore(score, coverage))
  // The measurement most responsible for the shortfall, but only when there is a real
  // shortfall to explain. Marking one on a part that scored 98 would invent a fault, and
  // marking one on a part scored from a few seconds would present those seconds as the
  // reason for a score about the whole recording.
  const driver = note ? undefined : metrics.find((m) => m.scored && m.shortfall >= 1)
  // The measurements' averages come from the same few seconds as the withheld score, so
  // they are withheld with it. Their names stay, so it is still clear what would have been
  // measured.
  const rows: ChannelMetric[] = note ? metrics.map((m) => ({ ...m, meanScore: null })) : metrics

  return (
    <div className="breakdown-channel">
      <div className="breakdown-head">
        <strong>{CHANNEL_NAME[channel]}</strong>
        <span className="n">{shown ?? '—'}</span>
      </div>
      {note && <div className="thin-note">{note}</div>}
      {metrics.length === 0 ? (
        <div className="muted" style={{ fontSize: 13 }}>
          Nothing could be measured here.
        </div>
      ) : (
        rows.map((m) => (
          <div
            key={m.metric}
            className={`metric ${channel}${m.scored ? '' : ' unscored'}${
              driver && m.metric === driver.metric ? ' driver' : ''
            }`}
          >
            <div className="metric-line">
              <strong style={{ fontWeight: m.scored ? 600 : 500 }}>
                {m.label}
                {!m.scored && ' (not counted)'}
              </strong>
              <span className="v">{m.meanScore === null ? '—' : Math.round(m.meanScore)}</span>
            </div>
            <div className="bar">
              <i style={{ width: `${Math.max(0, Math.min(100, m.meanScore ?? 0))}%` }} />
            </div>
          </div>
        ))
      )}
    </div>
  )
}
