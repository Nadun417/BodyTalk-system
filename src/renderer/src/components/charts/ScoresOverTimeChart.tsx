import { Line } from 'react-chartjs-2'
import {
  Chart as ChartJS,
  LinearScale,
  PointElement,
  LineElement,
  Tooltip,
  Legend,
  Filler
} from 'chart.js'
import type { WindowScore, Channel } from '@shared/types'
import { clock, CHANNEL_NAME } from '../../lib/format'
import { useChartTheme } from '../../lib/chartTheme'

ChartJS.register(LinearScale, PointElement, LineElement, Tooltip, Legend, Filler)

/**
 * How each score moved through the video.
 *
 * The combined score is drawn thicker than the three channels it is made from, because it is
 * the one being summarised and the others explain it. Seeing them together is what makes a
 * dip meaningful: a drop in the combined line with only the hands falling underneath it says
 * something quite different from all three falling at once.
 *
 * Each point carries its own timestamp rather than being placed by its position in a list. A
 * window that could not be scored is stored as no rows at all, so plotting by position would
 * silently close the gap and show a stretch of video that was never analysed as though it
 * had been.
 */
export default function ScoresOverTimeChart({ windows }: { windows: WindowScore[] }): JSX.Element {
  const theme = useChartTheme()
  const channels: Channel[] = ['fused', 'face', 'pose', 'hands']

  const datasets = channels.map((channel) => ({
    label: CHANNEL_NAME[channel],
    data: windows
      .filter((w) => w.channel === channel)
      .map((w) => ({ x: w.tStartS, y: w.rawScore })),
    borderColor: theme.channel[channel],
    backgroundColor: theme.channel[channel],
    // The combined line is the one being explained, so it is drawn solid and the three it is
    // made from are held back a little. Four lines of equal weight is a thicket.
    borderWidth: channel === 'fused' ? 2.5 : 1.25,
    pointRadius: 0,
    pointHitRadius: 8,
    tension: 0.35,
    spanGaps: true
  }))

  return (
    <div className="chart-wrap" style={{ height: 260 }}>
      <Line
        data={{ datasets }}
        options={{
          responsive: true,
          maintainAspectRatio: false,
          interaction: { mode: 'index', intersect: false },
          scales: {
            y: {
              min: 0,
              max: 100,
              grid: { color: theme.grid },
              ticks: { stepSize: 25, color: theme.text }
            },
            x: {
              type: 'linear',
              grid: { display: false },
              ticks: { maxTicksLimit: 8, color: theme.text, callback: (v) => clock(Number(v)) }
            }
          },
          plugins: {
            legend: {
              position: 'top',
              align: 'end',
              labels: { boxWidth: 8, usePointStyle: true, color: theme.text }
            },
            tooltip: {
              callbacks: {
                title: (items) => clock(Number(items[0].parsed.x)),
                label: (item) => `${item.dataset.label}: ${Math.round(Number(item.parsed.y))}`
              }
            }
          }
        }}
      />
    </div>
  )
}
