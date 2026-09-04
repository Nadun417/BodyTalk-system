import { useEffect, useState } from 'react'
import type { Channel } from '@shared/types'

/**
 * The real colours behind the theme's names, for anything drawn on a canvas.
 *
 * Everywhere else in the app a colour is written as `var(--face)` and the browser works out
 * what that means. A chart cannot do that. It paints onto a canvas, which knows nothing about
 * stylesheets, so handing it `var(--face)` gives it a word it cannot read and it falls back to
 * black. The charts were drawn entirely in black for exactly this reason until it was noticed.
 *
 * So the values are looked up here, once, and passed to the charts as ordinary colours. They
 * are looked up again whenever the theme is switched, because the same names stand for
 * different colours in the light and dark themes and a chart drawn before the switch would
 * otherwise keep the old ones.
 */
export interface ChartTheme {
  channel: Record<Channel, string>
  text: string
  grid: string
}

function readTheme(): ChartTheme {
  const style = getComputedStyle(document.documentElement)
  const value = (name: string, fallback: string): string =>
    style.getPropertyValue(name).trim() || fallback
  return {
    channel: {
      face: value('--face', '#16a34a'),
      pose: value('--pose', '#ea580c'),
      hands: value('--hands', '#7c3aed'),
      fused: value('--fused', '#2563eb')
    },
    text: value('--muted', '#6b7280'),
    grid: 'rgba(128, 128, 128, 0.18)'
  }
}

export function useChartTheme(): ChartTheme {
  const [theme, setTheme] = useState<ChartTheme>(readTheme)

  useEffect(() => {
    // The theme is recorded as an attribute on the page itself, so watching that attribute is
    // the most direct way to know it changed, and it needs no message passing between screens.
    const observer = new MutationObserver(() => setTheme(readTheme()))
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['data-theme']
    })
    return () => observer.disconnect()
  }, [])

  return theme
}
