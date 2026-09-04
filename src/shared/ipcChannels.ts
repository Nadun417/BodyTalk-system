/**
 * The names of the messages the interface and the backend send each other.
 *
 * They live in one file so that both sides are always naming the same thing. Typing these
 * strings out at the point of use would work right up until one of them was misspelled,
 * and a misspelled channel name fails silently: the message is sent, nobody is listening,
 * and nothing happens at all.
 *
 * These messages are the only way the two halves of the app talk. The interface cannot
 * read files, reach the database or start the analysis by itself. Everything it needs, it
 * has to ask for through one of these, which keeps anything sensitive on the other side of
 * a boundary the interface cannot step over.
 */
export const IpcChannels = {
  /** Ask the backend to open the system file picker so a video can be chosen. */
  openVideoDialog: 'dialog:openVideo',
  /**
   * Check a chosen video is usable, without committing to anything.
   *
   * Separate from creating the session so the upload screen can check a file the moment it
   * is picked and say straight away if there is a problem, rather than letting somebody
   * choose their settings and press the button before finding out.
   */
  validateVideo: 'video:validate',
  /** Check the chosen video is usable, and start a new session if it is. */
  createSession: 'session:create',
  /**
   * Ask for the address the results screen can play a session's video from.
   *
   * The interface is never given a location on disk. It gets one of the app's own addresses,
   * which the backend answers with the file, so the video can be played without the screen
   * knowing or being able to reach anything on the machine. Comes back empty for a session
   * recorded before videos were kept.
   */
  videoUrl: 'session:videoUrl',
  /** Start analysing a session. */
  startAnalysis: 'analysis:start',
  /** Stop an analysis that is still running. */
  cancelAnalysis: 'analysis:cancel',
  /** Sent the other way, from backend to interface, to drive the progress screen. */
  analysisProgress: 'analysis:progress',
  /** Fetch the list of past sessions for the home screen. */
  listSessions: 'session:list',
  /** Fetch one full session, with its scores and comments, for the dashboard. */
  getSession: 'session:get',
  /** Delete a session along with every file belonging to it. */
  deleteSession: 'session:delete',
  /** Save the session out as a PDF report. */
  exportReport: 'report:export',
  /** Read and write the application settings. */
  getSettings: 'settings:get',
  setSettings: 'settings:set'
} as const

export type IpcChannel = (typeof IpcChannels)[keyof typeof IpcChannels]
