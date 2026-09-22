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
        lambda a, b: f"You looked away from the camera between {clock(a)} and {clock(b)}.",
        "Try to keep your eyes toward the camera. It reads as engagement.",
    )

    events += _events(
        face_windows,
        lambda w: None if w.liveliness is None else w.liveliness < 20,
        20.0,
        "face",
        "flat_expression",
        "low",
        lambda a, b: f"Your expression stayed quite still from {clock(a)} to {clock(b)}.",
        "A little natural variation, the odd nod or smile, keeps an interviewer with you.",
    )

    events += _events(
        face_windows,
        lambda w: None if w.stability is None else w.stability < 40,
        5.0,
        "face",
        "head_movement",
        "low",
        lambda a, b: f"Frequent head movement between {clock(a)} and {clock(b)}.",
        "A steadier head position comes across as composed.",
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
        lambda a, b: f"Nice natural smile around {clock(a)}.",
        "Keep those moments. They land well.",
    )


# --------------------------------------------------------------------------- pose rules


def pose_events(pose_windows: Sequence) -> list[Event]:
    """Leaning off upright, leaning to one side, and swaying.

    Worth being precise about what the first one covers. It is measured in the flat image,
    so it catches the head and shoulders drifting off an upright line, and it catches
    leaning sideways. It does **not** catch slouching forward, which is movement toward
    the camera and cannot be seen reliably from a single lens. The wording below is
    deliberately limited to what was actually observed.
    """
    events: list[Event] = []

    events += _events(
        pose_windows,
        lambda w: None if w.uprightness is None else w.uprightness < 40,
        3.0,
        "pose",
        "slouching",
        "medium",
        lambda a, b: f"Your head and shoulders drifted off an upright line between {clock(a)} and {clock(b)}.",
        "Reset tall through the spine. Imagine a string from the crown of your head.",
    )

    events += _events(
        pose_windows,
        lambda w: None if w.levelness is None else w.levelness < 40,
        10.0,
        "pose",
        "leaning_to_side",
        "low",
        lambda a, b: f"You leaned to one side between {clock(a)} and {clock(b)}.",
        "Square your shoulders to the camera now and then.",
    )

    events += _events(
        pose_windows,
        lambda w: None if w.sway is None else w.sway < 40,
        8.0,
        "pose",
        "restlessness",
        "low",
        lambda a, b: f"Noticeable swaying between {clock(a)} and {clock(b)}.",
        "Plant both feet and settle your base. Stillness reads as calm.",
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
        lambda a, b: f"Your hands could not be seen between {clock(a)} and {clock(b)}.",
        "Check your hands are inside the frame and well lit. Natural gestures support "
        "what you say.",
    )

    events += _events(
        hand_windows,
        lambda w: None if w.gesture_raw is None else w.gesture_raw < gesture_low,
        30.0,
        "hands",
        "low_gesture",
        "info",
        lambda a, b: f"Your hands stayed quite still for a long stretch from {clock(a)}.",
        "A few natural gestures help emphasise your key points.",
    )

    events += _events(
        hand_windows,
        lambda w: None if w.gesture_raw is None else w.gesture_raw > gesture_high,
        10.0,
        "hands",
        "excessive_gesture",
        "low",
        lambda a, b: f"A lot of hand movement between {clock(a)} and {clock(b)}.",
        "Let some points land without a gesture. The busier ones then carry more weight.",
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
        "A common habit. Resting your hands below shoulder level keeps the frame clean.",
    )

    return events


def all_events(face_windows: Sequence, pose_windows: Sequence, hand_windows: Sequence) -> list[Event]:
    """Every rule, in time order, which is the order the dashboard lists them in."""
    events = face_events(face_windows) + pose_events(pose_windows) + hand_events(hand_windows)
    return sorted(events, key=lambda e: (e.t_start_s, e.channel, e.type))


# ------------------------------------------------------------------- what to try next

#: How much each severity counts when deciding which channel needs attention most.
SEVERITY_WEIGHT = {"info": 0.0, "low": 1.0, "medium": 2.0}

CHANNEL_LABEL = {"face": "face and eye contact", "pose": "posture", "hands": "hand movement"}


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
                title=f"Work on your {CHANNEL_LABEL.get(channel, channel)}",
                body=f"{worst.message} {worst.suggestion}",
                basis_event_types=sorted(
                    {e.type for e in events if e.channel == channel and SEVERITY_WEIGHT.get(e.severity, 0)}
                ),
                detail=_detail_for(channel, channel_scores.get(channel), metric_reports),
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
        out.append(
            Recommendation(
                rank=len(out) + 1,
                channel=best,
                kind="maintain",
                title=f"Keep doing what you did with your {CHANNEL_LABEL.get(best, best)}",
                body="This was your strongest channel in this session. Whatever you were doing there, keep it.",
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
    return (
        f"Your steadiest measurement here was {best.label}, "
        f"averaging {best.mean_score:.0f} out of 100."
    )
