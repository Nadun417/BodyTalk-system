import { describe, it, expect } from 'vitest'
import { buildReportDocDefinition } from '../src/renderer/src/report/pdfReport'
import type { Session, AnalysisEvent } from '../src/shared/types'

const session: Session = {
  id: 1,
  createdAt: '2026-06-17T10:00:00.000Z',
  videoFilename: 'demo.mp4',
  videoDurationS: 60,
  analysisFps: 6,
  fusionMode: 'adaptive',
  overallScore: 78,
  status: 'complete'
}

describe('buildReportDocDefinition', () => {
  it('puts the video filename in the document title', () => {
    const doc = buildReportDocDefinition(session, [], [])
    expect(doc.info?.title).toContain('demo.mp4')
  })

  it('renders timestamped insights as bullet points', () => {
    const events: AnalysisEvent[] = [
      {
        tStartS: 30,
        tEndS: 45,
        channel: 'hands',
        type: 'out_of_frame',
        severity: 'info',
        message: 'Hands left the frame 0:30–0:45.',
        suggestion: 'Keep your hands visible.'
      }
    ]
    const doc = buildReportDocDefinition(session, [], events)
    expect(JSON.stringify(doc)).toContain('Hands left the frame')
  })

  it('handles the no-events case gracefully', () => {
    const doc = buildReportDocDefinition(session, [], [])
    expect(JSON.stringify(doc)).toContain('No notable events detected.')
  })
})
