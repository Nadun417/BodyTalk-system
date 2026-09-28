import type { AnalysisEvent } from '@shared/types'

/**
 * Findings grouped by kind, for the results screen.
 *
 * The analysis reports every occurrence separately, which is right for the record and wrong for
 * a reader. On one real session the same finding appeared five times in a row, each with the
 * same advice underneath, and reading "try keeping your head a little steadier" five times over
 * makes an app look as though it is not paying attention. Grouped, it is one line: what was
 * noticed, how often and for how long in all, the moments it happened as times to jump to, and
 * the tip once.
 *
 * Nothing is lost by grouping. Every occurrence is still there as a time on the line, and each
 * one still jumps the video to where it happened.
 */

/**
 * What each kind of finding is called when several of them are shown together.
 *
 * Each has to stay inside what the finding's own message claims, for the same reason the
 * messages do: "head turned away", never "looked away", because the analysis measures the head
 * and not the eyes. A kind not listed here, which could only come from a session saved by a
 * version of the app with different rules, falls back to its first message.
 */
export const FINDING_NAME: Record<string, string> = {
  looking_away: 'Head turned away from the camera',
  flat_expression: 'Expression barely changing',
  head_movement: 'Head moving around a lot',
  smile: 'Natural smiles',
  slouching: 'Head or upper body tilted to one side',
  leaning_to_side: 'One shoulder higher than the other',
  restlessness: 'Swaying from side to side',
  hands_out_of_frame: "Hands couldn't be seen",
  low_gesture: 'Hands very still',
  excessive_gesture: 'Hands very busy',
  hand_to_face: 'Hand up to the face'
}

export interface FindingGroup {
  type: string
  channel: AnalysisEvent['channel']
  severity: AnalysisEvent['severity']
  /** What the group is called on screen. */
  name: string
  /** The advice, said once for the group. Null when none came with it. */
  tip: string | null
  /** Every occurrence, in the order they happened. */
  moments: AnalysisEvent[]
  /** How long they lasted between them, in whole seconds. */
  totalS: number
}

/**
 * The order the groups are listed in: the things worth working on first, the things merely
 * worth knowing next, and the moments that went well last.
 *
 * Within each of those, the group that happened first comes first. A list ordered purely by
 * time, which is how the findings used to be shown, puts a good moment at 0:05 above a real
 * problem at 1:40, and a reader skimming the top of it gets the wrong picture of the session.
 */
function rank(group: FindingGroup): number {
  if (group.type === 'smile') return 3
  if (group.severity === 'medium') return 0
  if (group.severity === 'low') return 1
  return 2
}

export function groupFindings(events: AnalysisEvent[]): FindingGroup[] {
  const byType = new Map<string, FindingGroup>()
  const inOrder = [...events].sort((a, b) => a.tStartS - b.tStartS)

  for (const event of inOrder) {
    let group = byType.get(event.type)
    if (!group) {
      group = {
        type: event.type,
        channel: event.channel,
        severity: event.severity,
        name: FINDING_NAME[event.type] ?? event.message,
        tip: event.suggestion || null,
        moments: [],
        totalS: 0
      }
      byType.set(event.type, group)
    }
    group.moments.push(event)
  }

  const groups = [...byType.values()]
  for (const group of groups) {
    const seconds = group.moments.reduce((sum, m) => sum + Math.max(0, m.tEndS - m.tStartS), 0)
    group.totalS = Math.max(1, Math.round(seconds))
  }

  return groups.sort((a, b) => rank(a) - rank(b) || a.moments[0].tStartS - b.moments[0].tStartS)
}

/** "Once, for 8 seconds" or "5 times, 48 seconds in all". */
export function howOften(group: FindingGroup): string {
  const seconds = `${group.totalS} second${group.totalS === 1 ? '' : 's'}`
  const n = group.moments.length
  return n === 1 ? `Once, for ${seconds}` : `${n} times, ${seconds} in all`
}
