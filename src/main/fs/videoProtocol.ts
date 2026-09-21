import { protocol } from 'electron'
import { sourceVideoPath } from './storage'
import { videoFileResponse } from './videoResponse'

/**
 * Lets the results screen play a session's video without ever handling a file path.
 *
 * The interface is not allowed to read the disk, and the page it runs in is deliberately
 * locked down so that nothing can load from anywhere except the app's own files. A video
 * player needs a source, though, and a session's recording lives in the user's own data
 * folder rather than inside the app.
 *
 * The way through is an address of the app's own: the screen asks for `bodytalk://video/12`
 * and this turns that into the right file. The interface never learns where anything is kept,
 * and nothing outside the sessions folder can be reached, because the only thing taken from
 * the address is a session number. There is no path in it to point somewhere else with.
 *
 * How the file is handed over matters more than it looks. The player has to be able to ask
 * for part of a file, which is what lets it jump to the middle of a recording without loading
 * all of it first, and jumping to a moment is the whole point of the screen. This used to pass
 * the request on to Electron's own fetch in the belief that it answered those requests. It
 * does not for local files, and every jump went back to the start of the video. The partial
 * answers are now built in `videoResponse.ts`, which explains the details.
 */
export const VIDEO_SCHEME = 'bodytalk'

/** The address the interface uses for one session's recording. */
export function videoUrl(sessionId: number): string {
  return `${VIDEO_SCHEME}://video/${sessionId}`
}

/**
 * Announce the scheme before the app starts.
 *
 * This has to happen early, before any window exists. Electron decides what a scheme is
 * allowed to do when it is registered, and a video that can be skipped through needs to be
 * treated as a proper address rather than as something opaque.
 */
export function registerVideoScheme(): void {
  protocol.registerSchemesAsPrivileged([
    {
      scheme: VIDEO_SCHEME,
      privileges: { standard: true, secure: true, supportFetchAPI: true, stream: true }
    }
  ])
}

/** Start answering requests. Called once the app is ready. */
export function serveSessionVideos(): void {
  protocol.handle(VIDEO_SCHEME, async (request) => {
    const id = Number(new URL(request.url).pathname.replace(/^\//, ''))
    if (!Number.isInteger(id) || id <= 0) return new Response('Not found', { status: 404 })

    const file = sourceVideoPath(id)
    // A session recorded before videos were copied in has no file here. That is an ordinary
    // state, not a fault, and the screen says so rather than showing a broken player.
    if (!file) return new Response('No video saved for this session', { status: 404 })

    return videoFileResponse(file, request.headers.get('range'))
  })
}
