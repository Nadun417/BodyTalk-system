import { Line } from 'react-chartjs-2'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Tooltip,
  Legend,
  Title
} from 'chart.js'
import type { WindowScore, Channel } from '@shared/types'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Tooltip, Legend, Title)

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
export default function WeightOverTimeChart({ windows }: { windows: WindowScore[] }): JSX.Element {
  const channels: Channel[] = ['face', 'pose', 'hands']
  const timestamps = Array.from(new Set(windows.map((w) => w.tStartS))).sort((a, b) => a - b)

  const datasets = channels.map((ch) => {
    const byT = new Map(windows.filter((w) => w.channel === ch).map((w) => [w.tStartS, w.weight]))
    return {
      label: ch,
      data: timestamps.map((t) => byT.get(t) ?? null),
      borderColor: COLORS[ch],
      backgroundColor: COLORS[ch],
      tension: 0.25,
      spanGaps: true
    }
  })

  return (
    <div className="chart-wrap">
      <div className="label" style={{ marginBottom: 8 }}>
        Channel weight over time (adaptive fusion)
      </div>
      <Line
        data={{ labels: timestamps.map((t) => `${t.toFixed(1)}s`), datasets }}
        options={{
          responsive: true,
          interaction: { mode: 'index', intersect: false },
          scales: {
            y: { min: 0, max: 1, title: { display: true, text: 'weight' } },
            x: { title: { display: true, text: 'time' } }
          },
          plugins: { legend: { position: 'bottom' } }
        }}
      />
    </div>
  )
}
