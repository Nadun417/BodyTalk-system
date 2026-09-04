import type { Content, TDocumentDefinitions } from 'pdfmake/interfaces'
import type { Session, AnalysisEvent, Recommendation, ScoredChannel } from '@shared/types'
import { clock, shortDate, CHANNEL_NAME } from '../lib/format'

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
  windowCount: number
  /** The two charts, already drawn, as picture data. Absent if they could not be captured. */
  charts?: { scores?: string; weights?: string }
}

const CHANNELS: ScoredChannel[] = ['face', 'pose', 'hands']

const GREY = '#6b7280'
const INK = '#111827'
const BRAND = '#2563eb'

export function buildReportDocDefinition(input: ReportInput): TDocumentDefinitions {
  const { session, events, recommendations, windowCount, charts } = input
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
            ...CHANNELS.map((c) => scoreCell(CHANNEL_NAME[c], session.channelScores[c]))
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
            { text: r.body, style: 'cell' }
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
      foot: { fontSize: 8, color: GREY }
    },
    defaultStyle: { fontSize: 10, color: INK }
  }
}

/** One score, shown the way the results screen shows it. */
function scoreCell(label: string, score: number | null, lead = false): Content {
  return {
    stack: [
      { text: label.toUpperCase(), style: 'scoreLabel' },
      {
        text: score === null || score === undefined ? '—' : String(score),
        style: 'scoreValue',
        color: lead ? BRAND : INK
      }
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
