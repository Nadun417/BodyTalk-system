import type { TDocumentDefinitions } from 'pdfmake/interfaces'
import pdfMake from 'pdfmake/build/pdfmake'
import * as vfsFonts from 'pdfmake/build/vfs_fonts'

/**
 * Turns a document description into the actual bytes of a PDF.
 *
 * Kept apart from the description itself so that what the report says can be tested without
 * building a real PDF, and so this file can deal with the one awkward part: fonts.
 *
 * **The fonts are the offline question.** A PDF has to carry its typefaces, and the usual way
 * of feeding them to this library is to fetch them from the internet, which this app is not
 * allowed to do under any circumstances. They come instead from the copy that ships inside
 * the library itself, already on the machine. Nothing here reaches the network, and a
 * packaged copy of the app will produce the same document with the network cable pulled out.
 *
 * The awkwardness is that the library has moved that bundled copy around between versions and
 * exposes it differently depending on how it is loaded, so it is looked for in each of the
 * places it has been known to live rather than assumed.
 */
function loadBundledFonts(): void {
  const source = vfsFonts as unknown as Record<string, unknown>
  const candidates = [
    (source.pdfMake as { vfs?: unknown } | undefined)?.vfs,
    (source.default as { pdfMake?: { vfs?: unknown }; vfs?: unknown } | undefined)?.pdfMake?.vfs,
    (source.default as { vfs?: unknown } | undefined)?.vfs,
    source.vfs,
    source.default
  ]
  const vfs = candidates.find(
    (candidate) => candidate && typeof candidate === 'object' && Object.keys(candidate).length > 0
  )
  if (vfs) {
    ;(pdfMake as unknown as { vfs: unknown }).vfs = vfs
  }
}

loadBundledFonts()

/**
 * Build the PDF and hand back its bytes.
 *
 * The bytes go to the backend to be written, because the interface is not allowed to touch
 * the disk. That is also why this returns them rather than offering the user a download: a
 * download would put the file wherever the browser felt like, and this app says the file goes
 * where the user chose.
 */
export function renderPdf(doc: TDocumentDefinitions): Promise<Uint8Array> {
  return new Promise((resolve, reject) => {
    try {
      pdfMake.createPdf(doc).getBuffer((buffer: ArrayBuffer | Uint8Array) => {
        resolve(buffer instanceof Uint8Array ? buffer : new Uint8Array(buffer))
      })
    } catch (err) {
      reject(err instanceof Error ? err : new Error(String(err)))
    }
  })
}
