import type { Content, TDocumentDefinitions } from 'pdfmake/interfaces'
import type {
  Session,
  AnalysisEvent,
  ChannelMetric,
  Recommendation,
  ScoredChannel
} from '@shared/types'
import { clock, shortDate, thinNote, CHANNEL_NAME } from '../lib/format'

/**
 * Describes what goes in a session's PDF report, section by section.
 *
 * This sits on the interface side because that is where the session data and the charts
 * already are. Building the document in the backend instead would mean fetching all of it a
 * second time and drawing the charts again just to put them in a file.
 *
 * The interface turns this description into the actual PDF and then hands the finished bytes
 * to the backend to save. Same rule as everywhere else: the interface decides what the
 * document says, the backend is the only part that writes to the disk.
 *
 * This function only builds a description and reads nothing outside its arguments, which is
 * what makes it straightforward to test.
 *
 * **Nothing is written here that the analysis did not find.** Every sentence in the document
 * comes from the stored result: the same summary, the same observations, the same advice as
 * the screen shows. It is deliberately not a place where extra interpretation gets added on
 * the way out, because a document is the version that gets kept, forwarded and reread, and
 * anything overstated in it would outlive the session it came from.
 */

/** Everything the report needs, gathered by the screen that asks for it. */
export interface ReportInput {
  session: Session
  events: AnalysisEvent[]
  recommendations: Recommendation[]
  /** What each channel score was made of, so the report explains the numbers it prints. */
  channelMetrics: ChannelMetric[]
  windowCount: number
  /** The two charts, already drawn, as picture data. Absent if they could not be captured. */
  charts?: { scores?: string; weights?: string }
}

const CHANNELS: ScoredChannel[] = ['face', 'pose', 'hands']

const GREY = '#6b7280'
const INK = '#111827'
const BRAND = '#2563eb'

export function buildReportDocDefinition(input: ReportInput): TDocumentDefinitions {
  const { session, events, recommendations, channelMetrics, windowCount, charts } = input
  const modeName = session.fusionMode === 'adaptive' ? 'Adaptive' : 'Fixed'

  const content: Content[] = [
    { text: 'BodyTalk', style: 'brand' },
    { text: 'Practice session report', style: 'h1' },
    {
      text:
        `${shortDate(session.createdAt)}  ·  ${clock(session.videoDurationS)}  ·  ` +
        `${modeName} weighting` +
        (session.videoFilename ? `  ·  ${session.videoFilename}` : ''),
      style: 'sub',
      margin: [0, 2, 0, 14]
    }
  ]

  if (session.overallSummary) {
    content.push({ text: session.overallSummary, style: 'lead', margin: [0, 0, 0, 14] })
  }

  content.push(
    { text: 'Scores', style: 'h2' },
    {
      margin: [0, 4, 0, 6],
      table: {
        widths: ['*', '*', '*', '*'],
        body: [
          [
            scoreCell('Overall', session.overallScore, true),
            ...CHANNELS.map((c) =>
              scoreCell(
                CHANNEL_NAME[c],
                session.channelScores[c],
                false,
                thinNote(session.channelCoverage?.[c])
              )
            )
          ]
        ]
      },
      layout: 'noBorders'
    },
    {
      text: `Based on ${windowCount} seconds of analysed video at ${session.analysisFps} frames a second.`,
      style: 'note',
      margin: [0, 0, 0, 16]
    },
    ...chartSection('Scores over time', charts?.scores, 'How each score moved through the video.'),
    ...chartSection(
      'How much each signal counted',
      charts?.weights,
      session.fusionMode === 'adaptive'
        ? 'The three shares always add up to the whole. When a channel cannot be seen clearly ' +
            'its share shrinks and the others take over.'
        : 'Fixed weighting keeps the shares equal between whatever the camera could see.'
    ),
    { text: 'What we noticed', style: 'h2' }
  )

  if (events.length) {
    content.push({
      margin: [0, 6, 0, 16],
      table: {
        headerRows: 1,
        widths: [72, 54, '*'],
        body: [
          [
            { text: 'When', style: 'th' },
            { text: 'Channel', style: 'th' },
            { text: 'What was visible', style: 'th' }
          ],
          ...events.map((event) => [
            { text: `${clock(event.tStartS)}–${clock(event.tEndS)}`, style: 'cell' },
            { text: CHANNEL_NAME[event.channel], style: 'cell' },
            {
              style: 'cell',
              stack: event.suggestion
                ? [{ text: event.message }, { text: event.suggestion, style: 'note' }]
                : [{ text: event.message }]
            }
          ])
        ]
      },
      layout: 'lightHorizontalLines'
    })
  } else {
    content.push({
      text: 'Nothing stood out for long enough to report.',
      style: 'note',
      margin: [0, 6, 0, 16]
    })
  }

  if (channelMetrics.length) {
    content.push(
      { text: 'What made up each score', style: 'h2' },
      {
        text:
          'Each score above is an average of the measurements below it. The shortfall column ' +
          'is how many points out of 100 that measurement pulled its channel down by.',
        style: 'note',
        margin: [0, 2, 0, 8]
      },
      {
        table: {
          headerRows: 1,
          widths: ['*', 'auto', 'auto', 'auto'],
          body: [
            [
              { text: 'Measurement', style: 'th' },
              { text: 'Channel', style: 'th' },
              { text: 'Average', style: 'th' },
              { text: 'Shortfall', style: 'th' }
            ],
            ...channelMetrics.map((m) => [
              {
                // Saying so on the row itself rather than in a footnote. A reader skimming
                // the table would otherwise take this number for one that shaped the score.
                text: m.scored ? m.label : `${m.label} (not counted towards the score)`,
                style: 'cell'
              },
              { text: CHANNEL_NAME[m.channel], style: 'cell' },
              { text: m.meanScore === null ? '—' : String(Math.round(m.meanScore)), style: 'cell' },
              {
                text: m.scored ? m.shortfall.toFixed(1) : '—',
                style: 'cell'
              }
            ])
          ]
        },
        layout: 'lightHorizontalLines',
        margin: [0, 0, 0, 16]
      }
    )
  }

  if (recommendations.length) {
    content.push(
      { text: 'What to try next', style: 'h2' },
      {
        text: 'Ranked by what would make the most difference in the next take.',
        style: 'note',
        margin: [0, 2, 0, 8]
      },
      ...recommendations.map(
        (r): Content => ({
          margin: [0, 0, 0, 10],
          stack: [
            { text: `${r.rank}. ${r.title}`, style: 'adviceTitle' },
            { text: r.body, style: 'cell' },
            // Kept separate from the advice above it, as it is on screen: this sentence is
            // arithmetic and is never reworded by anything.
            ...(r.detail
              ? ([{ text: r.detail, style: 'note', margin: [0, 3, 0, 0] }] as Content[])
              : [])
          ]
        })
      )
    )
  }

  return {
    info: {
      title: `BodyTalk session report — ${shortDate(session.createdAt)}`,
      author: 'BodyTalk'
    },
    pageMargins: [40, 46, 40, 54],
    // Written at the foot of every page rather than once at the end, because a page of this
    // can easily be read on its own, and what the numbers do not mean should travel with them.
    footer: (page: number, pages: number): Content => ({
      margin: [40, 12, 40, 0],
      columns: [
        {
          text: 'Describes only what was visible in the recording. It is not an assessment of the person.',
          style: 'foot'
        },
        { text: `${page} of ${pages}`, style: 'foot', alignment: 'right', width: 60 }
      ]
    }),
    content,
    styles: {
      brand: { fontSize: 10, bold: true, color: BRAND },
      h1: { fontSize: 21, bold: true, color: INK, margin: [0, 2, 0, 0] },
      h2: { fontSize: 13, bold: true, color: INK, margin: [0, 6, 0, 0] },
      sub: { fontSize: 10, color: GREY },
      lead: { fontSize: 11.5, color: INK, lineHeight: 1.35 },
      note: { fontSize: 9, color: GREY },
      th: { fontSize: 9, bold: true, color: GREY, margin: [0, 4, 0, 4] },
      cell: { fontSize: 10, color: INK, margin: [0, 4, 0, 4] },
      adviceTitle: { fontSize: 11, bold: true, color: INK, margin: [0, 0, 0, 2] },
      scoreLabel: { fontSize: 8, color: GREY },
      scoreValue: { fontSize: 20, bold: true, color: INK },
      scoreNote: { fontSize: 7, color: GREY, margin: [0, 2, 8, 0] },
      foot: { fontSize: 8, color: GREY }
    },
    defaultStyle: { fontSize: 10, color: INK }
  }
}

/** One score, shown the way the results screen shows it. */
/**
 * One score in the row at the top of the report.
 *
 * A score resting on too little of the recording keeps its number, greyed, with the same
 * caveat the results screen shows underneath it. The printed report is often read on its own,
 * away from the screen, so it has to carry the warning itself rather than rely on the reader
 * having seen it elsewhere.
 */
function scoreCell(
  label: string,
  score: number | null,
  lead = false,
  note: string | null = null
): Content {
  return {
    stack: [
      { text: label.toUpperCase(), style: 'scoreLabel' },
      {
        text: score === null || score === undefined ? '—' : String(score),
        style: 'scoreValue',
        color: note ? GREY : lead ? BRAND : INK
      },
      ...(note ? [{ text: note, style: 'scoreNote' } as Content] : [])
    ],
    margin: [0, 6, 0, 6]
  }
}

/**
 * A chart, or an honest note in its place.
 *
 * The picture is captured from the chart the screen has already drawn. If that could not be
 * done the section says so rather than being left out silently, because the report screen
 * tells the user the charts are included and a document that quietly drops them would be
 * making that a lie.
 */
function chartSection(title: string, image: string | undefined, note: string): Content[] {
  return [
    { text: title, style: 'h2' },
    { text: note, style: 'note', margin: [0, 2, 0, 6] },
    image
      ? { image, width: 515, margin: [0, 0, 0, 16] }
      : {
          text: 'This chart could not be included in the document. It is on the results screen.',
          style: 'note',
          margin: [0, 0, 0, 16]
        }
  ]
}
