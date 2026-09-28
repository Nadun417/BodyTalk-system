"""Turning a run of scores into things worth saying, each tied to a moment in the video.

Scores on their own are not feedback. "Your posture scored 61" tells somebody nothing they
can act on. What helps is knowing that between 0:45 and 1:30 they were leaning to one side,
and what to do about it next time. That is what this file produces.

The single most important rule here is that **a behaviour has to persist before it counts**.
Everybody shifts in their seat, glances away, or lets a hand drift up for a second. Flagging
those would bury the real patterns in noise and would read as nagging. So every rule below
requires its condition to hold for a minimum stretch, and each minimum is chosen for the
behaviour rather than being one number applied to everything: a hand touching the face
registers after two seconds, hands held completely still needs thirty.

Two allowances make that work on real footage. A gap of up to a second inside an interval is
ignored, so one recovered frame in the middle of a long slouch does not split it into two
separate observations. And intervals ending within two seconds of each other are merged,
since telling somebody they leaned at 0:45 and again at 0:48 is really telling them once.

These are plain functions, deliberately. It is a list of conditions and the durations they
need, and writing it as anything more elaborate would obscure a set of rules that is short
enough to read in one sitting.

Everything produced here describes something that was seen, at a time it was seen, with a
suggestion attached. Nothing here says anybody was nervous, unconfident or unprepared, and
no rule should ever be added that does.

**How it is worded.** The person reading this is practising for an interview, is probably not
technical, and did not ask to be graded. So every sentence follows the same few rules, which
were written down after the first version was found hard to read by the person it was for:

- Talk to them: "you", everyday words, one idea to a sentence.
- Say what was seen and when, "from 0:40 to 0:52". Never why, and never how they felt or
  how they came across as a person.
- Say exactly what the measurement can see and no more. Several earlier messages claimed
  more: "you looked away" when only the turn of the head is measured, and "you leaned to one
  side" when what is measured is one shoulder sitting higher than the other.
- The tip is one thing to try, starting with a verb, and justified by what it does for the
  answer rather than by how it makes somebody seem. Earlier tips leaned on "comes across as
  composed" and "stillness reads as calm", which are claims about a person's manner.
- None of the app's own vocabulary. "Channel", "metric" and "score came out lowest" are
  words for the people who built it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterable, Sequence

from .metrics import explain_channel

#: How long a gap inside an interval can be before it breaks the interval in two.
GAP_TOLERANCE_S = 1.0
#: Intervals ending this close together are treated as one observation.
MERGE_WITHIN_S = 2.0


@dataclass
class Event:
    """One thing worth telling the user, tied to when it happened."""

    t_start_s: float
    t_end_s: float
    channel: str
    type: str
    severity: str  # "info" | "low" | "medium"
    message: str
    suggestion: str
    #: Where the wording of `suggestion` came from: "template" for the sentence written here,
    #: "llm" if a language model reworded it and the result passed its checks. `message` is
    #: never reworded, because it carries the times and the claim about what was seen.
    phrasing: str = "template"

    @property
    def duration_s(self) -> float:
        return self.t_end_s - self.t_start_s


def clock(seconds: float) -> str:
    """Seconds as m:ss, which is how a person reads a video position."""
    minutes, secs = divmod(int(round(seconds)), 60)
    return f"{minutes}:{secs:02d}"


def sustained_intervals(
    flags: Sequence[tuple[float, float, bool]],
    min_duration_s: float,
    gap_tolerance_s: float = GAP_TOLERANCE_S,
    merge_within_s: float = MERGE_WITHIN_S,
) -> list[tuple[float, float]]:
    """Find stretches where a condition held long enough to be worth mentioning.

    Takes one entry per window: its start, its end, and whether the condition was true.
    Returns the stretches that survive, as start and end times.

    Windows where the condition could not be evaluated at all should simply be left out of
    the input. They then read as gaps, and the tolerance below decides whether a short one
    breaks the run. That is the right behaviour: a second where the camera lost the hands
    is not evidence that the person stopped fidgeting, but nor is it evidence they carried
    on, so a brief one is tolerated and a long one ends the interval.
    """
    runs: list[tuple[float, float]] = []
    start: float | None = None
    last_end: float | None = None

    for t_start, t_end, active in flags:
        if active:
            if start is None:
                start = t_start
            elif last_end is not None and t_start - last_end > gap_tolerance_s:
                runs.append((start, last_end))  # the gap was too long, close it off
                start = t_start
            last_end = t_end
        elif start is not None and last_end is not None:
            if t_end - last_end > gap_tolerance_s:
                runs.append((start, last_end))
                start = None
                last_end = None

    if start is not None and last_end is not None:
        runs.append((start, last_end))

    merged: list[tuple[float, float]] = []
    for run in runs:
        if merged and run[0] - merged[-1][1] <= merge_within_s:
            merged[-1] = (merged[-1][0], run[1])
        else:
            merged.append(run)

    return [r for r in merged if r[1] - r[0] >= min_duration_s]


def _windows_where(
    windows: Iterable,
    condition: Callable,
) -> list[tuple[float, float, bool]]:
    """Run a test over every window, skipping the ones it cannot answer for.

    A condition returning None means "cannot say", which is different from "no". Those
    windows are dropped rather than counted as false, so missing evidence never quietly
    becomes evidence of absence.
    """
    out = []
    for window in windows:
        verdict = condition(window)
        if verdict is None:
            continue
        out.append((window.t_start_s, window.t_end_s, bool(verdict)))
    return out


def _events(
    windows: Iterable,
    condition: Callable,
    min_duration_s: float,
    channel: str,
    type_: str,
    severity: str,
    message: Callable[[float, float], str],
    suggestion: str,
) -> list[Event]:
    """The shape every rule below shares: test each window, keep the lasting stretches."""
    intervals = sustained_intervals(_windows_where(windows, condition), min_duration_s)
    return [
        Event(
            t_start_s=start,
            t_end_s=end,
            channel=channel,
            type=type_,
            severity=severity,
            message=message(start, end),
            suggestion=suggestion,
        )
        for start, end in intervals
    ]


# --------------------------------------------------------------------------- face rules


def face_events(face_windows: Sequence) -> list[Event]:
    """Looking away, a held-flat expression, restless head movement, and smiles."""
    events: list[Event] = []

    events += _events(
        face_windows,
        lambda w: None if w.facing is None else w.facing < 40,
        4.0,
        "face",
        "looking_away",
        "medium",
        # "Turned your head" and not "looked away": the measurement is the angle of the
        # head, and someone can look away with their head still or keep their eyes on the
        # lens while their head is turned.
        lambda a, b: f"You turned your head away from the camera from {clock(a)} to {clock(b)}.",
        "Try keeping your face toward the camera, as if it were the person asking.",
    )

    events += _events(
        face_windows,
        lambda w: None if w.liveliness is None else w.liveliness < 20,
        20.0,
        "face",
        "flat_expression",
        "low",
        lambda a, b: f"Your expression barely changed from {clock(a)} to {clock(b)}.",
        # No nod in this one. A nod is head movement, which another rule flags, and advice
        # that sets off a different piece of advice is worse than none.
        "Try letting your face react to what you're saying. An occasional smile or raised "
        "eyebrow is plenty.",
    )

    events += _events(
        face_windows,
        lambda w: None if w.stability is None else w.stability < 40,
        5.0,
        "face",
        "head_movement",
        "low",
        lambda a, b: f"Your head moved around a lot from {clock(a)} to {clock(b)}.",
        "Try keeping your head a little steadier, especially while you're making a point.",
    )

    events += smile_events(face_windows)
    return events


def smile_events(face_windows: Sequence, ratio: float = 1.12, min_duration_s: float = 1.5) -> list[Event]:
    """Moments where the mouth was noticeably wider than this person's own resting width.

    Compared against the speaker's own median for the session rather than a fixed number,
    because resting mouth widths differ between people and a fixed threshold would just
    favour some faces over others.

    This is the only rule here that reports something going *well*. It never affects any
    score: rewarding smiling would amount to advising people to grin their way through an
    interview, which is bad advice. It exists to point out a moment that landed.
    """
    widths = [w.mouth_width for w in face_windows if w.mouth_width is not None]
    if len(widths) < 5:
        return []
    ordered = sorted(widths)
    median = ordered[len(ordered) // 2]
    if median <= 0:
        return []

    return _events(
        face_windows,
        lambda w: None if w.mouth_width is None else w.mouth_width > ratio * median,
        min_duration_s,
        "face",
        "smile",
        "info",
        lambda a, b: f"You smiled naturally around {clock(a)}.",
        "Nice. Moments like that are worth keeping in your answers.",
    )


# --------------------------------------------------------------------------- pose rules


def pose_events(pose_windows: Sequence) -> list[Event]:
    """Leaning off upright, leaning to one side, and swaying.

    Worth being precise about what the first one covers. It is measured in the flat image,
    so it catches sideways tilt away from vertical, and it does **not** catch slouching
    forward, which is movement toward the camera and cannot be seen reliably from a single
    lens.

    It is also two things at once, whichever is worse: the head tilted off the line of the
    shoulders, and the shoulders tilted off the line of the hips. That means a tilted head
    alone can raise it while the body has not moved at all, so the message says "your head
    or upper body" rather than naming the shoulders. Saying the shoulders moved when
    only the head did is the kind of claim a user can see is wrong, and somebody who catches
    the app being wrong once has no reason to believe the rest of it.
    """
    events: list[Event] = []

    events += _events(
        pose_windows,
        lambda w: None if w.uprightness is None else w.uprightness < 40,
        3.0,
        "pose",
        "slouching",
        "medium",
        lambda a, b: f"Your head or upper body tilted to one side from {clock(a)} to {clock(b)}.",
        "Try sitting tall, with your head straight above your shoulders.",
    )

    events += _events(
        pose_windows,
        lambda w: None if w.levelness is None else w.levelness < 40,
        10.0,
        "pose",
        "leaning_to_side",
        "low",
        # What is measured is one shoulder sitting higher than the other, so that is what it
        # says. "You leaned to one side" used to be the message here, which both claimed more
        # than the measurement sees and was hard to tell apart from the tilt rule above.
        lambda a, b: f"One shoulder sat higher than the other from {clock(a)} to {clock(b)}.",
        "Try letting both shoulders drop and rest at the same height.",
    )

    events += _events(
        pose_windows,
        lambda w: None if w.sway is None else w.sway < 40,
        8.0,
        "pose",
        "restlessness",
        "low",
        lambda a, b: f"You swayed from side to side from {clock(a)} to {clock(b)}.",
        "Try planting both feet flat and keeping your weight even.",
    )

    return events


# -------------------------------------------------------------------------- hand rules


def hand_events(
    hand_windows: Sequence,
    gesture_low: float = 0.15,
    gesture_high: float = 0.5,
) -> list[Event]:
    """Hands not visible, too still, too busy, fidgeting, and hands at the face."""
    events: list[Event] = []

    # Measured on visibility rather than on a score, because when the hands cannot be
    # seen there is no score to test. Marked as information rather than as something done
    # badly, since not being visible is not a mistake the person has made.
    #
    # The wording here is deliberately about what was seen and not about why. It used to
    # say the hands were "out of frame", which sounds harmless but asserts a cause the
    # data cannot establish. All the visibility figure tells us is that the hand detector
    # found nothing. It says nothing about where the hands actually were.
    #
    # That distinction turned out to matter. Checking every occurrence across the test
    # footage found four where the hands genuinely had left the shot, and one where they
    # had not: on that recording the pose model placed both wrists inside the frame, with
    # high confidence, in every single frame of the thirty-eight seconds the app spent
    # telling the person to fix their framing. Their framing was fine. The hand detector
    # simply failed on that posture, and the advice pointed the wrong way, because acting
    # on it would have meant changing a camera setup that was already correct.
    #
    # It was the only piece of feedback in the system that explained an observation
    # rather than reporting one, and so the only one that could be flatly wrong rather
    # than merely unhelpful. Saying the hands could not be seen is true in all five cases.
    # The suggestion now names the two things a person can actually check, instead of
    # presuming which of them is at fault.
    events += _events(
        hand_windows,
        lambda w: w.visibility < 0.2,
        10.0,
        "hands",
        "hands_out_of_frame",
        "info",
        lambda a, b: f"Your hands couldn't be seen from {clock(a)} to {clock(b)}.",
        "If you use your hands while you talk, check they're inside the frame and well lit "
        "so your gestures show up.",
    )

    events += _events(
        hand_windows,
        lambda w: None if w.gesture_raw is None else w.gesture_raw < gesture_low,
        30.0,
        "hands",
        "low_gesture",
        "info",
        lambda a, b: f"Your hands stayed very still from {clock(a)} to {clock(b)}.",
        "Try using your hands now and then to mark a key point.",
    )

    events += _events(
        hand_windows,
        lambda w: None if w.gesture_raw is None else w.gesture_raw > gesture_high,
        10.0,
        "hands",
        "excessive_gesture",
        "low",
        lambda a, b: f"Your hands were very busy from {clock(a)} to {clock(b)}.",
        "Try letting some points land without a gesture, so the ones you do use stand out.",
    )

    # There is deliberately no fidgeting rule. The measurement proved too unstable to
    # act on, and it is treated in the literature as an anxiety indicator, which is not
    # something this project claims to detect. It is still measured, and the reasons it
    # was dropped are recorded, but nothing is said to the user on the strength of it.
    events += _events(
        hand_windows,
        lambda w: None if w.touch_raw is None else w.touch_raw > 0.5,
        2.0,
        "hands",
        "hand_to_face",
        "low",
        lambda a, b: f"Your hand came up to your face around {clock(a)}.",
        "A very common habit. Try resting your hands low between gestures.",
    )

    return events


def all_events(face_windows: Sequence, pose_windows: Sequence, hand_windows: Sequence) -> list[Event]:
    """Every rule, in time order, which is the order the dashboard lists them in."""
    events = face_events(face_windows) + pose_events(pose_windows) + hand_events(hand_windows)
    return sorted(events, key=lambda e: (e.t_start_s, e.channel, e.type))


# ------------------------------------------------------------------- what to try next

#: How much each severity counts when deciding which channel needs attention most.
SEVERITY_WEIGHT = {"info": 0.0, "low": 1.0, "medium": 2.0}

#: What each part of the analysis is called in a sentence. The face is "face and head"
#: because that is what its three measurements look at: where the head points, how much it
#: moves, and how much the expression changes. It used to be "face and eye contact", but eye
#: contact is the one thing it cannot see; the face analyser says so in as many words.
CHANNEL_LABEL = {"face": "face and head", "pose": "posture", "hands": "hands"}

#: The heading for a piece of advice, taken from the finding it is about.
#:
#: A heading that says what to do reads better than one naming a part of the body to "work
#: on", and the card already carries a badge saying which part it is. Only the findings that
#: can lead a piece of advice are here: the ones marked as information carry no weight in the
#: ranking, so they never do.
ADVICE_TITLE = {
    "looking_away": "Keep your face toward the camera",
    "flat_expression": "Let your face react more",
    "head_movement": "Keep your head a little steadier",
    "slouching": "Sit tall and straight",
    "leaning_to_side": "Keep your shoulders level",
    "restlessness": "Stay steady from side to side",
    "excessive_gesture": "Give your hands a rest now and then",
    "hand_to_face": "Keep your hands away from your face",
}


@dataclass
class Recommendation:
    """One suggestion for the "what to try next" panel."""

    rank: int
    channel: str
    kind: str  # "improve" | "maintain"
    title: str
    body: str
    #: which kinds of observation this advice was built from, so a reader of the saved
    #: result can trace a suggestion back to the events that produced it
    basis_event_types: list[str] = field(default_factory=list)
    #: Where the wording of `body` came from: "template" or "llm". `title` is never reworded.
    phrasing: str = "template"
    #: `body` split into the half that may be reworded and the half that may not.
    #:
    #: `observation` is what was seen and when. `advice` is what to do about it. They are
    #: joined into `body` for display, but only `advice` is ever handed to the rewording
    #: step, because a model given the whole sentence rewrites the observation too: on real
    #: output it dropped both times altogether, and turned a statement that
    #: something had been seen into an instruction to go and do it. Keeping the halves apart
    #: here is what makes that impossible rather than merely discouraged.
    observation: str = ""
    advice: str = ""
    #: Which measurement inside the channel actually produced this score, in one sentence
    #: with the numbers in it. Kept apart from `body` rather than joined onto it because
    #: `body` is advice and gets reworded, while this is arithmetic and must not be. The
    #: same separation already applies to an observation's message and its suggestion.
    detail: str | None = None


def recommendations(
    events: Sequence[Event],
    channel_scores: dict[str, float | None],
    limit: int = 3,
    metric_reports: dict[str, Sequence] | None = None,
    thin_channels: Sequence[str] = (),
) -> list[Recommendation]:
    """Rank the channels and turn the top ones into at most three things to try.

    A channel needs attention in proportion to how far short it fell *and* how much of the
    video was actually spent doing something worth mentioning. Either on its own misleads:
    a low score with nothing sustained behind it is usually a threshold being harsh, and a
    long run of trivial observations on an otherwise strong channel is not where somebody
    should spend their practice time.

    Positive observations carry no weight here, since a smile is not something to fix.

    The ranking is **entirely deterministic**. The same analysis must produce the same
    advice in the same order every time, or the comparison between fusion modes would be
    measuring this function's inconsistency as well as theirs.

    When the per-measurement breakdown is passed in, each suggestion also gets a sentence
    naming which measurement inside the channel actually produced the score. This matters
    more than it sounds. "Work on your face and eye contact" is close to useless when the
    eye contact was fine all the way through and the whole shortfall came from a still
    expression, and it is the kind of advice that teaches somebody to stop reading.

    `thin_channels` names channels whose score rests on too little of the recording to be
    compared with the others. They can still be the subject of advice about something that
    was actually observed, since an observation stands on its own evidence, but they are
    never held up as the strongest channel, because that claim would rest on a few seconds.
    Advice about one also goes without the sentence of averages that usually follows, since
    those averages come from the same few seconds as the score that is not being shown.
    """
    pressure: dict[str, float] = {}
    for channel, score in channel_scores.items():
        if score is None:
            continue
        seconds = sum(
            e.duration_s * SEVERITY_WEIGHT.get(e.severity, 0.0)
            for e in events
            if e.channel == channel
        )
        pressure[channel] = (100.0 - score) * seconds

    if not pressure:
        return []

    ordered = sorted(pressure.items(), key=lambda kv: (-kv[1], kv[0]))
    out: list[Recommendation] = []

    for channel, weight in ordered:
        if weight <= 0 or len(out) >= limit - 1:
            break
        worst = max(
            (e for e in events if e.channel == channel and SEVERITY_WEIGHT.get(e.severity, 0)),
            key=lambda e: (SEVERITY_WEIGHT[e.severity], e.duration_s),
            default=None,
        )
        if worst is None:
            continue
        out.append(
            Recommendation(
                rank=len(out) + 1,
                channel=channel,
                kind="improve",
                title=ADVICE_TITLE.get(
                    worst.type, f"Something to try with your {CHANNEL_LABEL.get(channel, channel)}"
                ),
                body=f"{worst.message} {worst.suggestion}",
                observation=worst.message,
                advice=worst.suggestion,
                basis_event_types=sorted(
                    {e.type for e in events if e.channel == channel and SEVERITY_WEIGHT.get(e.severity, 0)}
                ),
                detail=(
                    None
                    if channel in thin_channels
                    else _detail_for(channel, channel_scores.get(channel), metric_reports)
                ),
            )
        )

    # Always finish on something that went well. A list of nothing but faults is
    # discouraging and, more practically, people stop reading it.
    #
    # A channel already listed as something to work on cannot also be the thing to keep
    # doing. Telling somebody to fix their posture and then to carry on exactly as they
    # were with their posture is contradictory, and it happens easily: a channel can score
    # well overall and still have the most sustained trouble in it.
    already_named = {r.channel for r in out}
    scored = {
        c: s
        for c, s in channel_scores.items()
        if s is not None and c not in already_named and c not in thin_channels
    }
    if scored and len(out) < limit:
        best = max(scored.items(), key=lambda kv: (kv[1], kv[0]))[0]
        label = CHANNEL_LABEL.get(best, best)

        # Only called the best when it is. Because the part with advice against it is passed
        # over just above, this is often the best of what is left rather than the best
        # overall, and the summary at the top of the screen names the real best. The two
        # used to contradict each other on screen: "Your posture came out best" in the
        # summary, and "Your hands came out best" on this card. Before the wording was
        # rewritten the card said "This was your strongest channel" in every case, so it was
        # just as wrong, only less obviously. The ranking matches the summary's exactly,
        # thin parts excluded, so the two can never disagree about which part that is.
        ranked = {
            c: s for c, s in channel_scores.items() if s is not None and c not in thin_channels
        }
        overall_best = max(ranked.items(), key=lambda kv: (kv[1], kv[0]))[0]
        observation = (
            f"Your {label} came out best this time."
            if best == overall_best
            else f"Your {label} scored {scored[best]:.0f} out of 100."
        )
        out.append(
            Recommendation(
                rank=len(out) + 1,
                channel=best,
                kind="maintain",
                title="Keep this up",
                body=f"{observation} Whatever you did there, keep doing it.",
                # How the part scored is a fact about the session, so it is the observation
                # half and stays as written. Only the encouragement is advice.
                observation=observation,
                advice="Whatever you did there, keep doing it.",
                detail=_strength_for(best, metric_reports),
            )
        )

    return out


def _detail_for(
    channel: str,
    score: float | None,
    reports: dict[str, Sequence] | None,
) -> str | None:
    """The sentence naming which measurement held a channel back, when one did."""
    if not reports:
        return None
    return explain_channel(score, reports.get(channel) or [])


def _strength_for(channel: str, reports: dict[str, Sequence] | None) -> str | None:
    """The sentence naming what went best in a channel, for advice about keeping it up.

    "Keep doing what you did" is hard to act on without knowing what that was. Naming the
    measurement turns it into something repeatable.
    """
    if not reports:
        return None
    scored = [
        r for r in (reports.get(channel) or []) if r.scored and r.mean_score is not None
    ]
    if not scored:
        return None
    best = max(scored, key=lambda r: (r.mean_score, r.metric))
    # "Best result" rather than the earlier "steadiest measurement", which read as though it
    # were about keeping still whichever measurement it named.
    return f"Your best result here was {best.label}, at {best.mean_score:.0f} out of 100."
