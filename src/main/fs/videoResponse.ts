import { createReadStream } from 'fs'
import { stat } from 'fs/promises'
import { extname } from 'path'
import { Readable } from 'stream'

/**
 * Hands a video file to the player in pieces, which is what makes it possible to jump around in.
 *
 * A video player does not load a recording in one go. When the user picks a moment half way
 * through, the player asks for "the bytes from here onwards" and expects to get exactly those
 * back, marked as a part of the file rather than the whole of it (status 206, with a
 * Content-Range line saying which part). If the answer comes back as the whole file from the
 * beginning instead (status 200), the player reasonably concludes the file cannot be skipped
 * through, and every jump lands back at the start. That is exactly how the results screen
 * behaved before this existed.
 *
 * The obvious way to avoid writing this, passing the request on to Electron's own fetch, looks
 * as if it should work and does not. Measured on 21 Sep 2026 with Electron 33: asked for the
 * bytes from one million onwards, Electron's fetch of a local file answered with the whole file
 * and status 200. So the partial answer is built here, where it can be seen and tested.
 *
 * Nothing in here knows about Electron, sessions or addresses. It is given a file and the
 * request's Range line and returns the answer, which keeps it testable against a real file
 * without starting the app.
 */

/** The part of a file one request asked for, counted in bytes from zero, both ends included. */
export interface ByteRange {
  start: number
  end: number
}

/**
 * Work out which bytes a Range line is asking for.
 *
 * Three answers are possible, and they mean different things:
 *
 * - A range: serve that part of the file.
 * - `null`: there is no usable range in the request, so serve the whole file as an ordinary
 *   answer. This covers a missing line, one that cannot be read, and a request for several
 *   separate pieces at once. Players do not ask for several pieces, and sending the whole file
 *   is always a correct answer, just a slower one.
 * - `'unsatisfiable'`: the request is readable but starts past the end of the file. The honest
 *   answer is to say so (status 416) rather than to send something else.
 *
 * The forms that matter are `bytes=1000-` (from here to the end, which is what a player sends
 * when it jumps), `bytes=1000-1999` (this exact stretch) and `bytes=-500` (the last 500 bytes,
 * which some players use to read an index stored at the end of the file). An end past the last
 * byte is trimmed to the last byte rather than refused, as the web's rules for this require.
 */
export function parseByteRange(
  header: string | null,
  size: number
): ByteRange | null | 'unsatisfiable' {
  if (!header) return null
  const match = /^bytes=(\d*)-(\d*)$/.exec(header.trim())
  if (!match) return null
  const [, from, to] = match
  if (from === '' && to === '') return null

  const last = size - 1

  if (from === '') {
    // "The last N bytes". Asking for more than the file holds simply means all of it.
    const wanted = Number(to)
    if (wanted === 0 || size === 0) return 'unsatisfiable'
    return { start: Math.max(0, size - wanted), end: last }
  }

  const start = Number(from)
  if (start >= size) return 'unsatisfiable'
  const end = to === '' ? last : Math.min(Number(to), last)
  if (end < start) return null
  return { start, end }
}

/**
 * The kind of video each accepted file ending holds.
 *
 * These are the same types the browser engine would have given the file itself, so the player
 * sees what it saw before this module existed. An ending not listed gets the general-purpose
 * type, and the player works out the format from the file's contents, which it does anyway.
 */
const VIDEO_TYPES: Record<string, string> = {
  '.mp4': 'video/mp4',
  '.m4v': 'video/mp4',
  '.webm': 'video/webm',
  '.mov': 'video/quicktime',
  '.mkv': 'video/x-matroska'
}

/**
 * The answer to one request for a video file: the part it asked for, or the whole file.
 *
 * Every answer says `Accept-Ranges: bytes`, including the full-file one. That line is how the
 * player learns, from its very first request, that asking for pieces is allowed here.
 */
export async function videoFileResponse(
  file: string,
  rangeHeader: string | null
): Promise<Response> {
  const { size } = await stat(file)
  const type = VIDEO_TYPES[extname(file).toLowerCase()] ?? 'application/octet-stream'
  const range = parseByteRange(rangeHeader, size)

  if (range === 'unsatisfiable') {
    return new Response(null, {
      status: 416,
      headers: { 'Content-Range': `bytes */${size}`, 'Accept-Ranges': 'bytes' }
    })
  }

  const { start, end } = range ?? { start: 0, end: size - 1 }
  const headers: Record<string, string> = {
    'Content-Type': type,
    'Content-Length': String(size === 0 ? 0 : end - start + 1),
    'Accept-Ranges': 'bytes'
  }
  if (range) headers['Content-Range'] = `bytes ${start}-${end}/${size}`

  // An empty file has no bytes to stream, and asking the file reader for "byte 0 to byte -1"
  // would not mean anything sensible, so it gets an empty answer directly.
  const body =
    size === 0 ? null : (Readable.toWeb(createReadStream(file, { start, end })) as ReadableStream)

  return new Response(body, { status: range ? 206 : 200, headers })
}
