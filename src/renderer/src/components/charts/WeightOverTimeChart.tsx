import { Line } from 'react-chartjs-2'
import {
  Chart as ChartJS,
  LinearScale,
  PointElement,
  LineElement,
  Tooltip,
  Legend,
  Title
} from 'chart.js'
import type { WindowScore, ScoredChannel, FusionMode } from '@shared/types'

ChartJS.register(LinearScale, PointElement, LineElement, Tooltip, Legend, Title)

const COLORS: Record<string, string> = {
  face: '#6ad0ff',
  pose: '#ffb86b',
  hands: '#b58bff'
}

/**
 * Shows how much each channel counted for, second by second, across the whole video.
 *
 * This is the one chart that makes the weighting visible instead of leaving it as something
 * happening out of sight. When the hands go out of shot, their line drops away and the other
 * two rise to fill the gap, and the user can see for themselves that the score for that
 * stretch was not built on their gestures.
 *
 * It also does a job the scores cannot: it explains why a channel scored oddly. A low hand
 * score with the weight already near zero says the camera missed them, not that anything was
 * wrong with how the person gestured.
 */
/** Seconds as minutes and seconds, the way the rest of the results screen writes a time. */
function clock(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${String(s).padStart(2, '0')}`
}

/**
 * What to call the chart, which depends on which way the scores were combined.
 *
 * Worth getting right rather than assuming. The comparison between the two modes is the
 * point of the project, and a fixed-weight session presented under an "adaptive" heading
 * would be evidence for the wrong thing, in a screenshot that could easily end up in the
 * write-up.
 */
const HEADING: Record<FusionMode, string> = {
  adaptive: 'Channel weight over time (adaptive fusion)',
  fixed: 'Channel weight over time (fixed weighting)'
}

export default function WeightOverTimeChart({
  windows,
  fusionMode
}: {
  windows: WindowScore[]
  fusionMode: FusionMode
}): JSX.Element {
  const channels: ScoredChannel[] = ['face', 'pose', 'hands']

  const datasets = channels.map((ch) => ({
    label: ch,
    // Each point carries its own time rather than relying on its position in the list. A
    // window that could not be scored at all is stored as no rows, so the times are not
    // guaranteed to be an unbroken run of seconds, and plotting by position would quietly
    // close the gap and show a stretch of video that was never analysed as though it had
    // been.
    data: windows.filter((w) => w.channel === ch).map((w) => ({ x: w.tStartS, y: w.weight })),
    borderColor: COLORS[ch],
    backgroundColor: COLORS[ch],
    tension: 0.25,
    spanGaps: true
  }))

  return (
    <div className="chart-wrap">
      <div className="label" style={{ marginBottom: 8 }}>
        {HEADING[fusionMode]}
      </div>
      <Line
        data={{ datasets }}
        options={{
          responsive: true,
          interaction: { mode: 'index', intersect: false },
          scales: {
            y: { min: 0, max: 1, title: { display: true, text: 'weight' } },
            x: {
              type: 'linear',
              title: { display: true, text: 'time' },
              // A label for every window is unreadable by about a minute of video and
              // absurd by ten. Chart.js is left to choose which ones to draw, up to this
              // many, so the axis stays legible whatever the length of the recording.
              ticks: {
                maxTicksLimit: 12,
                callback: (value) => clock(Number(value))
              }
            }
          },
          plugins: { legend: { position: 'bottom' } }
        }}
      />
    </div>
  )
}
