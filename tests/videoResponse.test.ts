import { describe, it, expect, beforeAll, afterAll } from 'vitest'
import { mkdtempSync, writeFileSync, rmSync } from 'fs'
import { tmpdir } from 'os'
import { join } from 'path'
import { parseByteRange, videoFileResponse } from '../src/main/fs/videoResponse'

/**
 * Handing a video to the player in pieces.
 *
 * This is what jumping to a moment on the results screen depends on. When it was missing, the
 * player was sent the whole file every time it asked for part of one, decided the video could
 * not be skipped through, and sent every jump back to the start.
 */
describe('parseByteRange', () => {
  const size = 1000

  it('reads "from here to the end", which is what a player sends when it jumps', () => {
    expect(parseByteRange('bytes=400-', size)).toEqual({ start: 400, end: 999 })
  })

  it('reads an exact stretch', () => {
    expect(parseByteRange('bytes=100-199', size)).toEqual({ start: 100, end: 199 })
  })

  it('reads "the last N bytes"', () => {
    expect(parseByteRange('bytes=-300', size)).toEqual({ start: 700, end: 999 })
  })

  it('treats asking for more of the end than exists as asking for all of it', () => {
    expect(parseByteRange('bytes=-5000', size)).toEqual({ start: 0, end: 999 })
  })

  it('trims an end that runs past the file rather than refusing it', () => {
    expect(parseByteRange('bytes=900-5000', size)).toEqual({ start: 900, end: 999 })
  })

  it('says a start past the end of the file cannot be met', () => {
    expect(parseByteRange('bytes=1000-', size)).toBe('unsatisfiable')
    expect(parseByteRange('bytes=0-', 0)).toBe('unsatisfiable')
  })

  it('falls back to the whole file when there is no usable range', () => {
    expect(parseByteRange(null, size)).toBeNull()
    expect(parseByteRange('', size)).toBeNull()
    expect(parseByteRange('bytes=-', size)).toBeNull()
    expect(parseByteRange('items=0-10', size)).toBeNull()
    expect(parseByteRange('bytes=0-10,20-30', size)).toBeNull()
    expect(parseByteRange('bytes=500-100', size)).toBeNull()
  })
})

describe('videoFileResponse', () => {
  let dir: string
  let file: string
  // Every byte different from its neighbours, so a piece taken from the wrong place shows up.
  const content = Buffer.from(Array.from({ length: 5000 }, (_, i) => i % 251))

  beforeAll(() => {
    dir = mkdtempSync(join(tmpdir(), 'bodytalk-video-'))
    file = join(dir, 'source.mp4')
    writeFileSync(file, content)
  })

  afterAll(() => rmSync(dir, { recursive: true, force: true }))

  it('answers a request for part of the file with exactly that part', async () => {
    const res = await videoFileResponse(file, 'bytes=1000-')
    expect(res.status).toBe(206)
    expect(res.headers.get('content-range')).toBe('bytes 1000-4999/5000')
    expect(res.headers.get('content-length')).toBe('4000')
    expect(res.headers.get('accept-ranges')).toBe('bytes')
    const body = Buffer.from(await res.arrayBuffer())
    expect(body.equals(content.subarray(1000))).toBe(true)
  })

  it('includes both ends of an exact stretch', async () => {
    const res = await videoFileResponse(file, 'bytes=10-19')
    expect(res.status).toBe(206)
    const body = Buffer.from(await res.arrayBuffer())
    expect(body.equals(content.subarray(10, 20))).toBe(true)
  })

  it('sends the whole file when no part was asked for, and says parts may be asked for', async () => {
    const res = await videoFileResponse(file, null)
    expect(res.status).toBe(200)
    expect(res.headers.get('accept-ranges')).toBe('bytes')
    expect(res.headers.get('content-type')).toBe('video/mp4')
    expect(res.headers.get('content-range')).toBeNull()
    const body = Buffer.from(await res.arrayBuffer())
    expect(body.equals(content)).toBe(true)
  })

  it('refuses a start past the end and says how long the file is', async () => {
    const res = await videoFileResponse(file, 'bytes=9000-')
    expect(res.status).toBe(416)
    expect(res.headers.get('content-range')).toBe('bytes */5000')
  })
})
