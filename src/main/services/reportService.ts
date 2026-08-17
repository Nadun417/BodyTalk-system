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
 *
 * This part is finished. What is still missing is the rest of the chain around it, namely
 * the interface producing the bytes and the message that carries them here.
 */
export async function writeReportPdf(bytes: Uint8Array, savePath: string): Promise<void> {
  await writeFile(savePath, bytes)
}
