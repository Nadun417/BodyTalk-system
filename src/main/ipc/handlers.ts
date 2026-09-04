import { ipcMain, dialog, BrowserWindow, type IpcMainInvokeEvent } from 'electron'
import { IpcChannels } from '@shared/ipcChannels'
import type { AppSettings, FusionMode, ProgressUpdate } from '@shared/types'
import {
  createSession,
  validateVideo,
  analyse,
  cancelAnalysis,
  deleteSession
} from '../services/sessionService'
import {
  listSessions,
  getSession,
  getWindowScores,
  getEvents,
  getRecommendations
} from '../db/sessionRepo'
import { getSettings, setSettings } from '../db/settingsRepo'

/** Registers every IPC handler. The renderer reaches the backend through these only. */
export function registerIpcHandlers(): void {
  ipcMain.handle(IpcChannels.openVideoDialog, async () => {
    const res = await dialog.showOpenDialog({
      title: 'Select a practice interview video',
      properties: ['openFile'],
      filters: [{ name: 'Video', extensions: ['mp4', 'webm', 'mov', 'mkv'] }]
    })
    return res.canceled ? null : res.filePaths[0]
  })

  ipcMain.handle(IpcChannels.validateVideo, async (_e, videoPath: string) => {
    const settings = getSettings()
    return validateVideo(videoPath, settings.minDurationS)
  })

  ipcMain.handle(
    IpcChannels.createSession,
    async (_e, args: { videoPath: string; fusionMode: FusionMode }) => {
      // Checked again here even though the upload screen has already checked it. The
      // interface asking first is a courtesy to the user; this is the check that actually
      // decides, because a file can be deleted or replaced between choosing it and pressing
      // the button, and because nothing on this side should trust the interface to have
      // done its homework.
      const settings = getSettings()
      const validation = await validateVideo(args.videoPath, settings.minDurationS)
      if (!validation.ok) return { error: validation.reason ?? 'Invalid video' }
      const id = createSession({
        videoFilename: args.videoPath.split(/[\\/]/).pop() ?? args.videoPath,
        videoDurationS: validation.durationS ?? 0,
        analysisFps: settings.analysisFps,
        fusionMode: args.fusionMode
      })
      return { sessionId: id }
    }
  )

  ipcMain.handle(
    IpcChannels.startAnalysis,
    async (
      e: IpcMainInvokeEvent,
      args: { sessionId: number; fusionMode: FusionMode; videoPath?: string; selfTest?: boolean }
    ) => {
      const sender = e.sender
      const onProgress = (update: ProgressUpdate): void => {
        if (!sender.isDestroyed()) sender.send(IpcChannels.analysisProgress, update)
      }
      const settings = getSettings()
      // Every ending is reported as an answer rather than thrown. A thrown message does not
      // survive the trip to the interface unchanged, so the interface cannot tell one ending
      // from another by reading it, and cancelling ended up displayed as an internal error.
      try {
        await analyse({
          sessionId: args.sessionId,
          fusionMode: args.fusionMode,
          videoPath: args.videoPath,
          analysisFps: settings.analysisFps,
          selfTest: args.selfTest,
          onProgress
        })
        return {}
      } catch (err) {
        const message = (err as Error).message
        return message === 'cancelled' ? { cancelled: true } : { error: message }
      }
    }
  )

  ipcMain.handle(IpcChannels.cancelAnalysis, (_e, sessionId: number) => cancelAnalysis(sessionId))

  ipcMain.handle(IpcChannels.listSessions, () => listSessions())

  ipcMain.handle(IpcChannels.getSession, (_e, id: number) => {
    const session = getSession(id)
    if (!session) return null
    return {
      session,
      windows: getWindowScores(id),
      events: getEvents(id),
      recommendations: getRecommendations(id)
    }
  })

  /**
   * Delete a session, after asking whether that is really wanted.
   *
   * The asking happens here rather than on the screen that has the button, for the same
   * reason the video is checked again here rather than trusted from the upload screen: this
   * is the side that actually does the deleting, so this is the side that has to be sure. A
   * second screen added later cannot get it wrong, because it cannot reach the deletion
   * without going past this.
   *
   * Deleting is worth a question. It removes the scores, the feedback and the whole session
   * folder from the machine with nothing to undo it, and once the video is copied in
   * alongside them it takes a copy of somebody's recording too. The default answer is to do
   * nothing, so that a stray press of the keyboard cannot destroy a session.
   */
  ipcMain.handle(IpcChannels.deleteSession, async (e: IpcMainInvokeEvent, id: number) => {
    const session = getSession(id)
    if (!session) return { deleted: false }

    const question = {
      type: 'warning' as const,
      buttons: ['Delete', 'Cancel'],
      defaultId: 1,
      cancelId: 1,
      title: 'Delete this session?',
      message: `Delete the analysis of ${session.videoFilename}?`,
      detail:
        'Its scores, its feedback and everything saved in its folder are removed from this ' +
        'computer. This cannot be undone.'
    }
    const parent = BrowserWindow.fromWebContents(e.sender)
    const { response } = parent
      ? await dialog.showMessageBox(parent, question)
      : await dialog.showMessageBox(question)

    if (response !== 0) return { deleted: false }
    deleteSession(id)
    return { deleted: true }
  })

  ipcMain.handle(IpcChannels.exportReport, async (_e, _id: number) => {
    const win = BrowserWindow.getFocusedWindow()
    const res = await dialog.showSaveDialog(win!, {
      title: 'Save feedback report',
      defaultPath: 'bodytalk-report.pdf',
      filters: [{ name: 'PDF', extensions: ['pdf'] }]
    })
    if (res.canceled || !res.filePath) return { cancelled: true }
    // [Step 8] renderer builds + renders the doc (report/pdfReport.ts) → bytes over IPC →
    // The next step is reportService.writeReportPdf(bytes, res.filePath). The interface does
    // not produce the PDF bytes yet, so there is nothing to pass along at this point.
    return { error: 'PDF export is not finished yet.' }
  })

  ipcMain.handle(IpcChannels.getSettings, () => getSettings())
  ipcMain.handle(IpcChannels.setSettings, (_e, patch: Partial<AppSettings>) => setSettings(patch))
}
