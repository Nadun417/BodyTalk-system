import { contextBridge, ipcRenderer } from 'electron'
import { IpcChannels } from '@shared/ipcChannels'
import type {
  AppSettings,
  FusionMode,
  ProgressUpdate,
  Session,
  WindowScore,
  AnalysisEvent,
  AnalysisOutcome,
  DeleteOutcome,
  Recommendation,
  VideoValidation
} from '@shared/types'

export interface SessionDetail {
  session: Session
  windows: WindowScore[]
  events: AnalysisEvent[]
  recommendations: Recommendation[]
}

/**
 * Everything the interface is allowed to do, and nothing else.
 *
 * The interface runs as a web page, and a web page that can reach the file system or start
 * programs is a web page that can do a lot of damage if anything ever goes wrong in it.
 * So it gets none of that. What it gets is this list of specific requests it may make, each
 * one handled on the other side by code that decides whether and how to carry it out.
 *
 * Adding a function here widens what the interface can reach, so it is worth being
 * deliberate about anything new that goes in.
 */
const api = {
  openVideoDialog: (): Promise<string | null> => ipcRenderer.invoke(IpcChannels.openVideoDialog),

  validateVideo: (videoPath: string): Promise<VideoValidation> =>
    ipcRenderer.invoke(IpcChannels.validateVideo, videoPath),

  createSession: (args: {
    videoPath: string
    fusionMode: FusionMode
  }): Promise<{ sessionId?: number; error?: string }> =>
    ipcRenderer.invoke(IpcChannels.createSession, args),

  startAnalysis: (args: {
    sessionId: number
    fusionMode: FusionMode
    videoPath?: string
    selfTest?: boolean
  }): Promise<AnalysisOutcome> => ipcRenderer.invoke(IpcChannels.startAnalysis, args),

  cancelAnalysis: (sessionId: number): Promise<void> =>
    ipcRenderer.invoke(IpcChannels.cancelAnalysis, sessionId),

  /** Subscribe to processing progress; returns an unsubscribe function. */
  onProgress: (cb: (update: ProgressUpdate) => void): (() => void) => {
    const listener = (_e: unknown, update: ProgressUpdate): void => cb(update)
    ipcRenderer.on(IpcChannels.analysisProgress, listener)
    return () => ipcRenderer.removeListener(IpcChannels.analysisProgress, listener)
  },

  listSessions: (): Promise<Session[]> => ipcRenderer.invoke(IpcChannels.listSessions),

  getSession: (id: number): Promise<SessionDetail | null> =>
    ipcRenderer.invoke(IpcChannels.getSession, id),

  deleteSession: (id: number): Promise<DeleteOutcome> =>
    ipcRenderer.invoke(IpcChannels.deleteSession, id),

  exportReport: (id: number): Promise<{ cancelled?: boolean; error?: string }> =>
    ipcRenderer.invoke(IpcChannels.exportReport, id),

  getSettings: (): Promise<AppSettings> => ipcRenderer.invoke(IpcChannels.getSettings),

  setSettings: (patch: Partial<AppSettings>): Promise<AppSettings> =>
    ipcRenderer.invoke(IpcChannels.setSettings, patch)
}

contextBridge.exposeInMainWorld('bodytalk', api)

export type BodyTalkApi = typeof api
