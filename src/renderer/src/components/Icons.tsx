/**
 * The app's few icons, drawn here as lines rather than taken from a font.
 *
 * They used to be text characters (a gear, a sun and a crescent moon from the symbol range of
 * the character set). Each one was drawn by whichever installed font happened to have it, so
 * the three came out at different sizes and weights, the gear arrived tinted in colour, and on
 * the dark screen the sun turned into something closer to an asterisk. An icon font or an
 * icon library fetched from the internet would fix that, but this app never touches the
 * internet. So they are drawn here: all on the same 24-unit grid, all in the same line weight,
 * all in the colour of the text around them.
 *
 * Every one is hidden from screen readers, because the button it sits on carries the name.
 */

import type { ReactNode } from 'react'

type IconProps = { className?: string }

function Svg({ className, children }: IconProps & { children: ReactNode }): JSX.Element {
  return (
    <svg
      className={`icon${className ? ` ${className}` : ''}`}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {children}
    </svg>
  )
}

/**
 * The outline of an eight-toothed gear, worked out rather than typed in.
 *
 * Each tooth is four points: up from the root of the gear, across its flat top, and back down.
 * Writing it as a loop keeps the teeth exactly even, which by hand they would not be.
 */
function gearOutline(): string {
  const points: string[] = []
  const root = 7.2
  const tip = 9.8
  // Each tooth is 16 degrees across at its tip and 26 at its root, leaving a gap of 19 degrees
  // between neighbours. Wider teeth close the gaps up and the outline reads as a blob.
  for (let tooth = 0; tooth < 8; tooth++) {
    const centre = (tooth * Math.PI) / 4
    for (const [radius, offsetDegrees] of [
      [root, -13],
      [tip, -8],
      [tip, 8],
      [root, 13]
    ]) {
      const angle = centre + (offsetDegrees * Math.PI) / 180
      points.push(
        `${(12 + radius * Math.cos(angle)).toFixed(2)} ${(12 + radius * Math.sin(angle)).toFixed(2)}`
      )
    }
  }
  return `M${points.join('L')}Z`
}

const GEAR = gearOutline()

/** Eight rays around a small disc, each a short line starting clear of it. */
function sunRays(): string {
  const rays: string[] = []
  for (let i = 0; i < 8; i++) {
    const angle = (i * Math.PI) / 4
    const from = 7
    const to = 9.4
    rays.push(
      `M${(12 + from * Math.cos(angle)).toFixed(2)} ${(12 + from * Math.sin(angle)).toFixed(2)}` +
        `L${(12 + to * Math.cos(angle)).toFixed(2)} ${(12 + to * Math.sin(angle)).toFixed(2)}`
    )
  }
  return rays.join('')
}

const RAYS = sunRays()

export function GearIcon(props: IconProps): JSX.Element {
  return (
    <Svg {...props}>
      <path d={GEAR} />
      <circle cx="12" cy="12" r="3" />
    </Svg>
  )
}

export function SunIcon(props: IconProps): JSX.Element {
  return (
    <Svg {...props}>
      <circle cx="12" cy="12" r="4" />
      <path d={RAYS} />
    </Svg>
  )
}

export function MoonIcon(props: IconProps): JSX.Element {
  return (
    <Svg {...props}>
      {/* A large arc for the outer edge of the crescent, and a smaller one cutting back in. */}
      <path d="M20 14.5A8.5 8.5 0 1 1 9.5 4a7.5 7.5 0 0 0 10.5 10.5z" />
    </Svg>
  )
}

/** A screen on a stand, for "Match Windows". */
export function MonitorIcon(props: IconProps): JSX.Element {
  return (
    <Svg {...props}>
      <rect x="3" y="4" width="18" height="12.5" rx="2" />
      <path d="M8.5 20h7M12 16.5V20" />
    </Svg>
  )
}
