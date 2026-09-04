import { describe, it, expect } from 'vitest'
import { buildReportDocDefinition, type ReportInput } from '../src/renderer/src/report/pdfReport'
import type { Session, AnalysisEvent, Recommendation } from '../src/shared/types'

/**
 * What the exported document says.
 *
 * The document is the version of a session that gets kept, forwarded and reread long after
 * the app is closed, so what it claims matters more than what any screen claims. These tests
 * are mostly about restraint: that it carries the findings across unchanged, and that it does
 * not quietly drop a section it promised or add a judgement nobody made.
 *
 * Only the description of the document is built here, never a real PDF, which is what makes
 * it testable at all.
 */
const session: Session = {
  id: 1,
  createdAt: '2026-06-17T10:00:00.000Z',
  videoFilename: 'demo.mp4',
  videoDurationS: 143,
  analysisFps: 6,
  fusionMode: 'adaptive',
  overallScore: 78,
  channelScores: { face: 66.4, pose: 98.3, hands: 71.4 },
  overallSummary: 'Your strongest channel this session was posture.',
  status: 'complete'
}

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

const recommendations: Recommendation[] = [
  {
    rank: 1,
    channel: 'face',
    kind: 'improve',
    title: 'Work on your face and eye contact',
    body: 'Your expression stayed quite still.',
    basisEventTypes: ['flat_expression']
  }
]

const build = (over: Partial<ReportInput> = {}): string =>
  JSON.stringify(
    buildReportDocDefinition({
      session,
      events,
      recommendations,
      windowCount: 143,
      charts: { scores: 'data:image/png;base64,AAA', weights: 'data:image/png;base64,BBB' },
      ...over
    })
  )

describe('buildReportDocDefinition', () => {
  it('names the session in the document title', () => {
    const doc = buildReportDocDefinition({ session, events, recommendations, windowCount: 143 })
    expect(doc.info?.title).toContain('2026')
  })

  it('carries the observations across word for word', () => {
    expect(build()).toContain('Hands left the frame')
  })

  it('carries the advice across, in the order it was ranked', () => {
    expect(build()).toContain('1. Work on your face and eye contact')
  })

  it('includes the summary the analysis wrote', () => {
    expect(build()).toContain('Your strongest channel this session was posture.')
  })

  it('includes every score, and says which weighting produced them', () => {
    const doc = build()
    for (const score of ['78', '66.4', '98.3', '71.4']) expect(doc).toContain(score)
    expect(doc).toContain('Adaptive weighting')
  })

  it('embeds both charts when they were captured', () => {
    const doc = build()
    expect(doc).toContain('data:image/png;base64,AAA')
    expect(doc).toContain('data:image/png;base64,BBB')
  })

  /**
   * The report screen tells the user the charts are included. If one could not be captured the
   * document has to say so rather than closing the gap silently, or the screen has told them
   * something untrue.
   */
  it('says a chart is missing rather than dropping the section', () => {
    const doc = build({ charts: { scores: undefined, weights: undefined } })
    expect(doc).toContain('could not be included')
  })

  /**
   * The one sentence that is not from the analysis, and it is a disclaimer. It goes on every
   * page because a single page of this can be read on its own, and what the numbers do not
   * mean has to travel with them.
   */
  it('states on the page that it describes behaviour and not the person', () => {
    const doc = buildReportDocDefinition({ session, events, recommendations, windowCount: 143 })
    const footer = doc.footer as (page: number, pages: number) => unknown
    expect(JSON.stringify(footer(1, 2))).toContain('not an assessment of the person')
  })

  it('copes with a session that produced nothing to report', () => {
    const doc = build({ events: [], recommendations: [] })
    expect(doc).toContain('Nothing stood out')
    expect(doc).not.toContain('What to try next')
  })

  it('shows a dash where a score was never recorded', () => {
    const doc = build({
      session: { ...session, channelScores: { face: null, pose: null, hands: null } }
    })
    expect(doc).toContain('—')
  })
})
