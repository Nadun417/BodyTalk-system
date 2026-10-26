import { writeFile } from 'fs/promises'

/**
 * Saving the finished PDF report to wherever the user chose to put it.
 *
 * The report is built on the interface side, because that is where the charts and the
 * finished numbers already are, and rebuilding them here purely to draw a PDF would mean
 * keeping two copies of the same logic in step with each other.
 *
 * The interface hands over the finished PDF as raw bytes and this writes them out. That
 * split keeps to the same rule as everywhere else in the app: the interface decides what
 * the document should say, and the backend is the only part that touches the disk.
 */

/** What happened when a report was saved: where it went, or a sentence saying why it did not. */
export type SaveOutcome = { savedTo: string } | { error: string }

/**
 * Write the report and say how it went, without ever throwing.
 *
 * A save can fail for reasons that have nothing to do with BodyTalk: the file is open in a PDF
 * viewer, the folder is one Windows will not let a program write to, the drive is full, or the
 * folder has gone. Each of those is turned into a sentence the person can act on. The first
 * version passed on the system's own text instead, and in testing that produced "EBUSY:
 * resource busy or locked, open '…'", which is accurate and tells a person nothing.
 *
 * Nothing about the session is touched here, so a failed save leaves the session exactly as it
 * was.
 */
export async function saveReportPdf(bytes: Uint8Array, savePath: string): Promise<SaveOutcome> {
  if (!bytes?.byteLength) return { error: 'The report came through empty and was not saved.' }
  try {
    await writeFile(savePath, bytes)
    return { savedTo: savePath }
  } catch (err) {
    return { error: whySaveFailed((err as NodeJS.ErrnoException).code) }
  }
}

/** The plain-words reason for a failed save, from the system's error code. */
export function whySaveFailed(code: string | undefined): string {
  switch (code) {
    case 'EBUSY':
      return (
        'The report could not be saved because a file with that name is open in another ' +
        'program. Close it, or save the report under a different name.'
      )
    case 'EPERM':
    case 'EACCES':
    case 'EROFS':
      return (
        'The report could not be saved because that folder cannot be written to, or a file ' +
        'with that name is open elsewhere. Try another folder, such as Documents.'
      )
    case 'ENOENT':
      return 'The report could not be saved because that folder no longer exists. Choose another folder.'
    case 'ENOSPC':
      return 'The report could not be saved because the drive is full. Free some space, or choose another drive.'
    default:
      return 'The report could not be saved there. Try another folder or another file name.'
  }
}
