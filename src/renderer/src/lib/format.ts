import type { Channel, ChannelCoverage } from '@shared/types'

/**
 * The small conversions every screen needs, kept together so they agree with each other.
 *
 * They are here rather than repeated per screen because the same second has to be written
 * the same way wherever it appears. A moment listed as 0:30 in the findings, marked at 0:30
 * on the video scrubber and labelled 0:30 on the chart is only obviously the same moment if
 * all three were written by the same function.
 */

/** Seconds as minutes and seconds, the way a video player writes a time. */
export function clock(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return '0:00'
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${String(s).padStart(2, '0')}`
}

/**
 * The caveat for a channel score that rests on too little of the recording, or null.
 *
 * Written once here so the results screen and the PDF say exactly the same thing. It says
 * how little was scored and not why: the channel may have been out of shot, hidden or simply
 * not picked up, and the analysis cannot tell those apart, so the sentence does not pretend
 * to. Whether the score counts as thin was decided by the analysis, not here.
 */
export function thinNote(coverage: ChannelCoverage | null | undefined): string | null {
  if (!coverage?.thin) return null
  return `Only ${coverage.windows} of ${coverage.of} seconds could be scored, so treat this as a hint.`
}

/** A stored timestamp as a short date, in the reader's own regional format. */
export function shortDate(iso: string): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return '—'
  return date.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })
}

/**
 * Which of three broad bands a score falls in, used to colour it.
 *
 * Deliberately coarse. These scores come from thresholds that have only ever been calibrated
 * against one person's recordings, so shading them finely would suggest a precision the
 * numbers do not have. Three bands say "this went well", "this was mixed" and "this is worth
 * looking at", which is as much as can honestly be claimed.
 */
export function band(score: number | null | undefined): 'good' | 'fair' | 'poor' | 'none' {
  if (score === null || score === undefined) return 'none'
  if (score >= 75) return 'good'
  if (score >= 55) return 'fair'
  return 'poor'
}

/** The colour a channel is drawn in, the same everywhere it appears. */
export const CHANNEL_COLOUR: Record<Channel, string> = {
  face: 'var(--face)',
  pose: 'var(--pose)',
  hands: 'var(--hands)',
  fused: 'var(--fused)'
}

/** What a channel is called on screen, avoiding the words used inside the code. */
export const CHANNEL_NAME: Record<Channel, string> = {
  face: 'Face',
  pose: 'Posture',
  hands: 'Hands',
  fused: 'Overall'
}
