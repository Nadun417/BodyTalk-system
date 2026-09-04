import { Bar } from 'react-chartjs-2'
import { Chart as ChartJS, LinearScale, CategoryScale, BarElement, Tooltip, Legend } from 'chart.js'
import type { WindowScore, ScoredChannel, FusionMode } from '@shared/types'
import { clock, CHANNEL_NAME } from '../../lib/format'
import { useChartTheme } from '../../lib/chartTheme'

ChartJS.register(LinearScale, CategoryScale, BarElement, Tooltip, Legend)

const CHANNELS: ScoredChannel[] = ['face', 'pose', 'hands']

/** How many columns to divide the video into. */
const BUCKETS = 14

/**
 * How much each channel counted towards the score, across the video.
 *
 * This is the picture the whole project is arguing for, so it is worth saying why it is drawn
 * this way. The three weights always add up to the whole, and a stacked column says that in
 * a way three separate lines never can: when one channel's block shrinks, the others visibly
 * take up the space it left. That is the behaviour being claimed, shown rather than asserted.
 *
 * The columns are stretches of video rather than single seconds. At one column per second a
 * two-minute video would be a hundred and twenty slivers, which is unreadable and says nothing
 * a coarser view does not. Averaging over a stretch also matches what actually matters: a
 * channel dropping out for a moment is noise, and a channel dropping out for ten seconds is
 * the thing worth seeing.
 *
 * In fixed mode the columns are near enough equal all the way across, which is not a fault in
 * the drawing. It is what fixed weighting means, and having the two modes drawn the same way
 * is what makes them comparable.
 */
export default function WeightOverTimeChart({
  windows,
  fusionMode
}: {
  windows: WindowScore[]
  fusionMode: FusionMode
}): JSX.Element {
  const theme = useChartTheme()
  const times = windows.map((w) => w.tStartS)
  const end = times.length ? Math.max(...times) : 0
  const width = end > 0 ? end / BUCKETS : 1

  // Average each channel's weight over each stretch, ignoring windows where the channel was
  // not scored at all so that a gap does not read as a weight of zero.
  const buckets = Array.from({ length: BUCKETS }, (_, i) => {
    const from = i * width
    const to = (i + 1) * width
    const inRange = windows.filter(
      (w) => w.tStartS >= from && (w.tStartS < to || i === BUCKETS - 1)
    )
    const share: Record<string, number> = {}
    for (const channel of CHANNELS) {
      const values = inRange
        .filter((w) => w.channel === channel && w.weight !== null)
        .map((w) => w.weight as number)
      share[channel] = values.length ? values.reduce((a, b) => a + b, 0) / values.length : 0
    }
    // Drawn as a percentage of the whole so every column is full height and the comparison
    // between columns is about the split rather than about how much was measured.
    const total = CHANNELS.reduce((sum, c) => sum + share[c], 0) || 1
    return {
      label: clock(from),
      face: (100 * share.face) / total,
      pose: (100 * share.pose) / total,
      hands: (100 * share.hands) / total
    }
  })

  return (
    <div className="chart-wrap" style={{ height: 240 }}>
      <Bar
        data={{
          labels: buckets.map((b) => b.label),
          datasets: CHANNELS.map((channel) => ({
            label: CHANNEL_NAME[channel],
            data: buckets.map((b) => b[channel]),
            backgroundColor: theme.channel[channel],
            borderWidth: 0,
            borderRadius: 2
          }))
        }}
        options={{
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            x: {
              stacked: true,
              grid: { display: false },
              ticks: { maxTicksLimit: 8, color: theme.text }
            },
            y: {
              stacked: true,
              min: 0,
              max: 100,
              ticks: { stepSize: 25, color: theme.text, callback: (v) => `${v}%` },
              grid: { color: theme.grid }
            }
          },
          plugins: {
            legend: {
              position: 'top',
              align: 'start',
              labels: { boxWidth: 8, usePointStyle: true, color: theme.text }
            },
            tooltip: {
              callbacks: {
                label: (item) => `${item.dataset.label}: ${Math.round(Number(item.parsed.y))}%`,
                footer: () =>
                  fusionMode === 'adaptive'
                    ? 'Shares move with how clearly each channel could be seen.'
                    : 'Fixed weighting: shares stay equal between whatever was visible.'
              }
            }
          }
        }}
      />
    </div>
  )
}
