import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { resolve } from 'path'

/**
 * The BodyTalk icon.
 *
 * Windows shows it on the program, the installer, the taskbar and the title bar, and the app shows
 * it in its top bar. Both are made from one master picture by scripts/make_icon.py, so they are
 * the same icon. These tests check the pieces that would fail silently: an icon file missing a
 * size Windows asks for, an installer setting pointing somewhere else, or a master or logo that
 * has gone missing or lost its shape. Without the icon, the installer builder falls back to
 * Electron's own without saying anything.
 */
const root = resolve(__dirname, '..')

describe('the icon file', () => {
  const ico = readFileSync(resolve(root, 'build/icon.ico'))

  it('is an icon file', () => {
    expect(ico.readUInt16LE(0)).toBe(0) // reserved
    expect(ico.readUInt16LE(2)).toBe(1) // 1 means an icon, 2 would be a cursor
  })

  const sizes = Array.from({ length: ico.readUInt16LE(4) }, (_, n) => {
    const entry = 6 + 16 * n
    const width = ico.readUInt8(entry) || 256 // the format writes 256 as 0
    const length = ico.readUInt32LE(entry + 8)
    const offset = ico.readUInt32LE(entry + 12)
    return { width, length, offset }
  })

  it('holds every size Windows asks for, from the title bar to a large desktop', () => {
    const widths = sizes.map((s) => s.width)
    for (const size of [16, 20, 24, 32, 40, 48, 64, 256]) expect(widths).toContain(size)
  })

  it('stores each size as a complete picture inside the file', () => {
    const PNG = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a])
    for (const { length, offset } of sizes) {
      expect(offset + length).toBeLessThanOrEqual(ico.length)
      expect(ico.subarray(offset, offset + 8).equals(PNG)).toBe(true)
    }
  })
})

describe('the installer settings', () => {
  const config = readFileSync(resolve(root, 'electron-builder.yml'), 'utf-8')

  it('give the program, the installer and the uninstaller the BodyTalk icon', () => {
    for (const key of ['icon', 'installerIcon', 'uninstallerIcon']) {
      expect(config).toMatch(new RegExp(`^\\s+${key}: build/icon\\.ico$`, 'm'))
    }
  })
})

/** Width and height of a PNG, read from the header every PNG starts with. */
function pngSize(file: Buffer): { width: number; height: number } {
  expect(file.subarray(12, 16).toString('latin1')).toBe('IHDR')
  return { width: file.readUInt32BE(16), height: file.readUInt32BE(20) }
}

describe('the pictures the icon is made from and shown as', () => {
  /**
   * The master is what every size is made from. It has to be square, or the icon comes out
   * squashed, and large enough that the biggest size in the icon file is a reduction rather
   * than an enlargement.
   */
  it('keeps a square master, larger than the largest size in the icon', () => {
    const { width, height } = pngSize(readFileSync(resolve(root, 'build/icon-source.png')))
    expect(width).toBe(height)
    expect(width).toBeGreaterThanOrEqual(256)
  })

  it('gives the app a square logo large enough for the sharpest screens', () => {
    const { width, height } = pngSize(
      readFileSync(resolve(root, 'src/renderer/src/assets/logo.png'))
    )
    expect(width).toBe(height)
    // Shown at 32 by 32, so four times that keeps it sharp at 400 per cent display scaling.
    expect(width).toBeGreaterThanOrEqual(128)
  })
})
