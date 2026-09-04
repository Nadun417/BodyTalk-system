/**
 * The shapes of data that both halves of the application need to agree on.
 *
 * The backend and the interface are separate programs that pass messages to each other, so
 * they need a shared idea of what a session or a score actually looks like. Defining that
 * once here means a change to the shape is a change in one file, rather than two versions
 * quietly drifting apart until something breaks at run time.
 *
 * This file deliberately imports nothing. Both sides pull it in, so anything added here
 * gets loaded into both, including the interface where very little should be running.
 */

export type FusionMode = 'adaptive' | 'fixed'

/**
 * The three things actually measured. `fused` is what they combine into, not a fourth
 * measurement, which is why it is kept separate: anything that loops over the channels that
 * were observed wants these three and would double-count with `fused` in the list.
 */
export type ScoredChannel = 'face' | 'pose' | 'hands'

export type Channel = ScoredChannel | 'fused'

/**
 * The score for each channel across a whole session, as the analysis calculated it.
 *
 * These are carried through rather than worked out again from the per-window scores, and
 * that is deliberate. A window where a channel could not be measured has no score, and the
 * average has to skip it rather than treat it as a zero. Working the average out a second
 * time somewhere else is how that distinction gets lost: a channel that was simply out of
 * shot for a while ends up looking like a channel that performed badly, which is the one
 * conclusion this project exists to avoid drawing.
 *
 * Null means the value was not recorded. Sessions analysed before these were stored have
 * nothing here, and showing nothing is the honest answer for them.
 */
export type ChannelScores = Record<ScoredChannel, number | null>

export type SessionStatus = 'pending' | 'processing' | 'complete' | 'error' | 'cancelled'

export type Severity = 'info' | 'low' | 'medium' | 'high'

/** One attempt at analysing one video. */
export interface Session {
  id: number
  createdAt: string
  videoFilename: string
  videoDurationS: number
  analysisFps: number
  fusionMode: FusionMode
  overallScore: number | null
  channelScores: ChannelScores
  /**
   * The sentence that sums up the session, written by the analysis from what it found.
   * Null for sessions recorded before it was stored, and for the self-test, which does not
   * produce one.
   */
  overallSummary: string | null
  status: SessionStatus
}

/**
 * How a piece of text in the results came to be worded.
 *
 * `template` means it was assembled from fixed wording. The intention is that a small
 * language model can later reword these into something that reads more naturally, and this
 * records which of the two produced any given line. That record matters: the model is only
 * ever allowed to reword a finding the analysis already made, never to decide what the
 * finding is, and without this there would be no way to show afterwards which was which.
 */
export type Phrasing = 'template' | 'model'

/**
 * One piece of advice for the user, worked out from the events that were detected.
 *
 * Nothing here is a fresh observation. `kind` says whether it is something to work on or
 * something that went well and is worth keeping, and `basisEventTypes` names the detected
 * events it was built from, so any advice on screen can be traced back to something that
 * was actually seen in the video.
 */
export interface Recommendation {
  rank: number
  channel: Channel
  kind: string
  title: string
  body: string
  basisEventTypes: string[]
  phrasing?: Phrasing
}

/**
 * The scores for one channel over one second of video.
 *
 * `visibility` and `weight` are saved for every single window, and they should stay that
 * way. They are the record of how clearly each channel could be seen and how much say it
 * was given as a result, which is both what the weight chart is drawn from and the only
 * evidence that the adaptive weighting did anything. Dropping them to save space would
 * throw away the results this project exists to produce.
 */
export interface WindowScore {
  tStartS: number
  tEndS: number
  channel: Channel
  rawScore: number
  visibility: number | null
  weight: number | null
}

/** Something noticeable that happened over a stretch of the video. */
export interface AnalysisEvent {
  tStartS: number
  tEndS: number
  channel: Channel
  type: string
  severity: Severity
  /**
   * Describes what was visible and nothing more. "Your hands were out of shot" is fine.
   * Anything about how the person seemed, felt, or would fare in a real interview is not,
   * because none of it can be told apart from the alternatives by looking at landmarks.
   */
  message: string
  suggestion: string
  /** How this wording was produced. See `Phrasing`. */
  phrasing?: Phrasing
}

/** Settings the user can change, kept between runs. */
export interface AppSettings {
  analysisFps: number
  reportSavePath: string | null
  minDurationS: number
}

/** A progress update passed along from the pipeline so the screen can keep moving. */
export interface ProgressUpdate {
  sessionId: number
  stage: string
  done: number
  total: number
}

/**
 * Everything the pipeline produces for one run.
 *
 * The channel scores are optional because the self-test does not produce them. It exists to
 * prove the two programs can talk to each other without needing the detection libraries
 * installed, so it returns the smallest result that exercises that path rather than a
 * complete one.
 */
export interface PipelineResult {
  fusionMode: FusionMode
  overallScore: number
  channelScores?: ChannelScores
  overallSummary?: string
  summaryPhrasing?: Phrasing
  windows: WindowScore[]
  events: AnalysisEvent[]
  recommendations?: Recommendation[]
}

/**
 * How an analysis ended.
 *
 * All three endings come back as an ordinary answer rather than as a thrown error, and that
 * is the point of this type. A message thrown in the backend does not arrive in the
 * interface as it was written: it gets wrapped, so what set out as "cancelled" arrives as
 * "Error invoking remote method 'analysis:start': Error: cancelled". Code on the other side
 * that recognises an ending by its wording therefore fails to recognise it, and the user
 * who pressed Cancel was left watching a progress bar with the app's internal plumbing
 * quoted underneath it.
 *
 * Cancelling is not a failure in any case. It is a thing the user chose to do, and it reads
 * oddly to treat it as an error anywhere in the code.
 *
 * Nothing set means it finished: the scores are saved and the results are ready to open.
 */
export interface AnalysisOutcome {
  /** The user pressed Cancel. Nothing was saved, and there is nothing to apologise for. */
  cancelled?: boolean
  /** Something went wrong, phrased for the person who has to read it. */
  error?: string
}

/**
 * What happened when a session was asked to be deleted.
 *
 * `deleted` is false when the user was asked to confirm and said no, which is an ordinary
 * answer rather than a failure. The screen uses it to decide whether the list it is showing
 * has actually changed.
 */
export interface DeleteOutcome {
  deleted: boolean
}

/** The answer to "is this video usable?", checked before any analysis starts. */
/**
 * The answer to "can this video be analysed?", produced before any analysis starts.
 *
 * The check itself runs in Python, because that is the only side of the app that can open a
 * video file at all. It takes a couple of seconds, which is the point: an unusable file is
 * refused straight away rather than after several minutes of processing.
 */
export interface VideoValidation {
  ok: boolean
  /**
   * A short tag naming which check failed, so the interface never has to match on wording.
   * One of: ok, not_found, unreadable, too_short, no_person. It is also set to
   * check_failed when the check itself could not be run, which is not the same as the video
   * being bad and is deliberately not treated as a refusal.
   */
  code?: string
  /** The sentence shown to the user. Empty when the video was accepted. */
  reason?: string
  durationS?: number
  width?: number
  height?: number
  sourceFps?: number
  /**
   * Things worth telling the user that are not grounds for refusing the file, such as the
   * warning that only one person is ever analysed. Shown alongside an accepted video.
   */
  warnings?: string[]
}
