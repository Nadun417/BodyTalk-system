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
      return analyse({
        sessionId: args.sessionId,
        fusionMode: args.fusionMode,
        videoPath: args.videoPath,
        analysisFps: settings.analysisFps,
        selfTest: args.selfTest,
        onProgress
      })
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

  ipcMain.handle(IpcChannels.deleteSession, (_e, id: number) => deleteSession(id))

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
