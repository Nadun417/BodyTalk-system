import type { TDocumentDefinitions } from 'pdfmake/interfaces'
import type { Session, WindowScore, AnalysisEvent } from '@shared/types'

/**
 * Describes what should go in a session's PDF report, section by section.
 *
 * This sits on the interface side because that is where the session data and the charts
 * already are. Building the document in the backend instead would mean fetching all of it
 * a second time and drawing the charts again just to put them in a file.
 *
 * The interface turns this description into the actual PDF and then hands the finished
 * bytes to the backend to save. Same rule as everywhere else: the interface decides what
 * the document says, the backend is the only part that writes to the disk.
 *
 * This function only builds a description and reads nothing outside its arguments, which
 * makes it straightforward to test. Turning that description into a real PDF, and drawing
 * the charts into it, comes later.
 */
export function buildReportDocDefinition(
  session: Session,
  _windows: WindowScore[],
  events: AnalysisEvent[]
): TDocumentDefinitions {
  return {
    info: { title: `BodyTalk Report — ${session.videoFilename}` },
    content: [
      { text: 'BodyTalk — Body Language Feedback', style: 'h1' },
      { text: session.videoFilename, style: 'sub' },
      {
        text: `Overall score: ${session.overallScore ?? 'n/a'}  ·  Fusion: ${session.fusionMode}`,
        margin: [0, 8, 0, 8]
      },
      { text: 'Timestamped insights', style: 'h2' },
      {
        // These come straight from the analysis and are already worded to describe what
        // was visible. Nothing is added here that the analysis did not actually find.
        ul: events.length
          ? events.map((e) => `${fmt(e.tStartS)}–${fmt(e.tEndS)} · ${e.message} → ${e.suggestion}`)
          : ['No notable events detected.']
      }
    ],
    styles: {
      h1: { fontSize: 20, bold: true },
      h2: { fontSize: 14, bold: true, margin: [0, 12, 0, 4] },
      sub: { fontSize: 11, color: '#666' }
    },
    defaultStyle: { fontSize: 10 }
  }
}

function fmt(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${String(s).padStart(2, '0')}`
}
