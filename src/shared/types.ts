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
  status: SessionStatus
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
  windows: WindowScore[]
  events: AnalysisEvent[]
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
