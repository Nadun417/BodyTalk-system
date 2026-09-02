"""The hand channel: two sets of 21 hand landmarks reduced to one score from 0 to 100.

Three measurements go into the hand score:

  gesture activity  are the hands moving a natural amount, too little, or far too much?
  fidgeting         are there small repetitive movements, the kind that read as restless?
  hand to face      how much of the time is a hand up at the nose or chin?

One measurement is deliberately kept out of the score. How often the hands are in frame at
all is recorded as this channel's visibility, and the fusion stage already lowers the
channel's influence when that drops. Letting it push the score down as well would punish
the same thing twice, and it would be punishing camera framing rather than behaviour.

Gesture activity is scored against a band rather than a straight better-or-worse line.
Hands held rigidly still read as stiff, hands thrown about constantly read as distracting,
and the comfortable range sits between the two. It is the only measurement here that does
not use the usual two-point scale.

This channel cannot stand on its own. Hand positions mean nothing without a sense of scale,
which comes from the shoulders, and hand-to-face needs to know where the face is. So the
analyser reads pose and face landmarks too, and abstains from whichever measurement it is
missing the supporting data for rather than guessing at it.

A note on what the sampling rate allows. At roughly six frames a second, movement faster
than about three cycles a second cannot be made out at all. Fidgeting here therefore means
repetitive movement slow enough to be seen at that rate, not a fine tremor. That is a real
limit of the method and is worth stating as one rather than glossing over.

Everything measured is a position or a speed. Nothing here infers nerves, confidence or
mood, and a low score should never be read that way.
"""

from __future__ import annotations

import math
import statistics as stats
from dataclasses import dataclass

from .base import AnalysisResult, Analyser, Window, dist, presence_rate, scale, square

# --- positions of the landmarks used ---------------------------------------------------
WRIST = 0  # in the 21-point hand model
FINGERTIPS = (4, 8, 12, 16, 20)  # thumb through to little finger
FACE_NOSE_TIP = 1  # in the 468-point face mesh
FACE_CHIN = 152
FACE_CHEEK_RIGHT = 234
FACE_CHEEK_LEFT = 454
POSE_SHOULDER_LEFT = 11  # in the 33-point body model
POSE_SHOULDER_RIGHT = 12

HAND_KEYS = ("leftHand", "rightHand")


def band_score(
    value: float,
    too_low: float,
    low_ok: float,
    high_ok: float,
    too_high: float,
    floor: float = 40.0,
) -> float:
    """Score a measurement that can be wrong in either direction.

    Anything between `low_ok` and `high_ok` is comfortable and scores 100. At or beyond
    `too_low` and `too_high` the score sits at the floor. In between it slides.

    The floor is deliberately not zero. Hands held very still and hands moving constantly
    are both worth mentioning, but neither is a disaster, and a zero would say otherwise.
    """
    if low_ok <= value <= high_ok:
        return 100.0
    if value < low_ok:
        if value <= too_low:
            return floor
        return floor + (100.0 - floor) * (value - too_low) / (low_ok - too_low)
    if value >= too_high:
        return floor
    return floor + (100.0 - floor) * (too_high - value) / (too_high - high_ok)


@dataclass
class HandsWindow:
    """Everything worked out for one window, not just the final answer."""

    index: int
    t_start_s: float
    t_end_s: float
    visibility: float
    score: float | None
    # the three sub-scores, 0 to 100, or None when the supporting data was missing
    gesture: float | None
    fidget: float | None
    touch: float | None
    # the raw measurements those sub-scores were calculated from
    gesture_raw: float | None  # wrist travel per second, in shoulder widths
    fidget_raw: float | None  # small direction reversals per second
    touch_raw: float | None  # fraction of the window with a hand at the face
    shoulder_width: float | None


class HandsAnalyser(Analyser):
    """Turns windows of hand landmarks into a hand score from 0 to 100.

    Stateful, because speed needs a previous position to compare against and that position
    is often in the window before. One instance handles one video, fed in order.

    Every threshold is a starting point awaiting calibration, so they are all constructor
    arguments rather than fixed numbers buried in the maths.
    """

    channel = "hands"

    def __init__(
        self,
        aspect: float,
        # gesture activity, in shoulder widths of wrist travel per second
        gesture_too_low: float = 0.05,
        gesture_low_ok: float = 0.15,
        gesture_high_ok: float = 0.5,
        gesture_too_high: float = 0.85,
        # fidgeting: small direction reversals per second
        # Calibrated 2 Sep 2026. Ordinary talking with the hands produces about 3 small
        # reversals a second and deliberate fidgeting about 4, so the bad end sits above
        # both rather than below them. The two are only 1.3x apart, which makes this the
        # least confident measurement in the project - see the calibration log.
        fidget_bad: float = 4.5,
        fidget_good: float = 1.0,
        fidget_max_step: float = 0.12,  # a longer step is a gesture, not a fidget
        # A step shorter than this is landmark jitter rather than real movement. Without
        # it a completely motionless hand scored as the most fidgety thing in the corpus,
        # because a still wrist wobbles randomly by a pixel or two every frame and every
        # one of those wobbles counted as a change of direction.
        fidget_min_step: float = 0.01,
        # hand to face: a fingertip closer than this many face widths counts as contact
        touch_distance: float = 0.6,
        touch_bad: float = 0.5,  # a hand at the face for half the window scores 0
        touch_good: float = 0.0,
    ) -> None:
        self.aspect = aspect
        self.gesture_too_low = gesture_too_low
        self.gesture_low_ok = gesture_low_ok
        self.gesture_high_ok = gesture_high_ok
        self.gesture_too_high = gesture_too_high
        self.fidget_bad = fidget_bad
        self.fidget_good = fidget_good
        self.fidget_max_step = fidget_max_step
        self.fidget_min_step = fidget_min_step
        self.touch_distance = touch_distance
        self.touch_bad = touch_bad
        self.touch_good = touch_good

        #: last seen wrist position and time per hand, carried across window boundaries
        self._previous: dict[str, tuple[float, tuple[float, float]]] = {}

    # --------------------------------------------------------- measurements per frame

    def _shoulder_width(self, window: Window) -> float | None:
        """Distance between the shoulders, averaged over the window.

        Hand movement has to be measured against the size of the person on screen,
        otherwise simply sitting closer to the camera would look like gesturing harder.
        """
        widths = [
            dist(
                f["pose"]["landmarks"][POSE_SHOULDER_LEFT],
                f["pose"]["landmarks"][POSE_SHOULDER_RIGHT],
                self.aspect,
            )
            for f in window.frames
            if f["pose"]["detected"]
        ]
        widths = [w for w in widths if w > 0]
        return stats.fmean(widths) if widths else None

    def _touching_face(self, frame: dict) -> bool | None:
        """Is any fingertip up at the nose or chin in this frame?

        Returns None when the face was not detected. "We could not check" and "we checked
        and the answer is no" are different answers, and merging them would quietly turn
        missing evidence into a clean bill of health.
        """
        if not frame["face"]["detected"]:
            return None
        face = frame["face"]["landmarks"]
        face_width = dist(face[FACE_CHEEK_RIGHT], face[FACE_CHEEK_LEFT], self.aspect)
        if face_width <= 0:
            return None

        nose = square(face[FACE_NOSE_TIP], self.aspect)
        chin = square(face[FACE_CHIN], self.aspect)
        limit = self.touch_distance * face_width

        for key in HAND_KEYS:
            if not frame[key]["detected"]:
                continue
            hand = frame[key]["landmarks"]
            for tip_index in FINGERTIPS:
                tip = square(hand[tip_index], self.aspect)
                if min(math.dist(tip, nose), math.dist(tip, chin)) < limit:
                    return True
        return False

    # ---------------------------------------------------- putting a window together

    def _nothing_seen(self, window: Window, visibility: float) -> HandsWindow:
        """No hands anywhere in this window, so no score.

        A zero would claim poor gesturing when the truth is the hands were never in shot.
        The remembered wrist positions are cleared too, so that when the hands reappear the
        first frame does not get credited with a huge jump in speed.
        """
        self._previous.clear()
        return HandsWindow(
            index=window.index,
            t_start_s=window.t_start_s,
            t_end_s=window.t_end_s,
            visibility=visibility,
            score=None,
            gesture=None,
            fidget=None,
            touch=None,
            gesture_raw=None,
            fidget_raw=None,
            touch_raw=None,
            shoulder_width=None,
        )

    def analyse_detail(self, window: Window) -> HandsWindow:
        """Score one window and hand back the full working-out."""
        visibility = presence_rate(window, *HAND_KEYS)
        if visibility <= 0:
            return self._nothing_seen(window, visibility)

        shoulder_width = self._shoulder_width(window)

        travel: list[float] = []  # distance covered per second, one entry per step
        steps: dict[str, list[tuple[float, float]]] = {key: [] for key in HAND_KEYS}

        for frame in window.frames:
            for key in HAND_KEYS:
                if not frame[key]["detected"]:
                    continue
                position = square(frame[key]["landmarks"][WRIST], self.aspect)
                previous = self._previous.get(key)
                self._previous[key] = (frame["tS"], position)
                if previous is None:
                    continue
                previous_t, previous_position = previous
                gap = frame["tS"] - previous_t
                if gap <= 0:
                    continue
                dx = position[0] - previous_position[0]
                dy = position[1] - previous_position[1]
                travel.append(math.hypot(dx, dy) / gap)
                steps[key].append((dx, dy))

        # Fidgeting is a change of direction over a *short* step. Changing direction in the
        # middle of a broad gesture is just gesturing; it is the small repetitive reversals
        # that read as restless, so longer steps are excluded before counting.
        reversals = 0
        if shoulder_width:
            limit = self.fidget_max_step * shoulder_width
            floor_step = self.fidget_min_step * shoulder_width
            for key in HAND_KEYS:
                sequence = steps[key]
                for i in range(1, len(sequence)):
                    dx0, dy0 = sequence[i - 1]
                    dx1, dy1 = sequence[i]
                    size0, size1 = math.hypot(dx0, dy0), math.hypot(dx1, dy1)
                    if size0 > limit or size1 > limit:
                        continue
                    if size0 < floor_step or size1 < floor_step:
                        continue
                    if dx0 * dx1 < 0 or dy0 * dy1 < 0:
                        reversals += 1

        duration = max(window.t_end_s - window.t_start_s, 1e-6)

        gesture_raw: float | None = None
        gesture: float | None = None
        fidget_raw: float | None = None
        fidget: float | None = None
        if shoulder_width and travel:
            gesture_raw = stats.fmean(travel) / shoulder_width
            gesture = band_score(
                gesture_raw,
                self.gesture_too_low,
                self.gesture_low_ok,
                self.gesture_high_ok,
                self.gesture_too_high,
            )
            fidget_raw = reversals / duration
            fidget = scale(fidget_raw, self.fidget_bad, self.fidget_good)

        checked = [self._touching_face(f) for f in window.frames]
        checked = [c for c in checked if c is not None]
        touch_raw: float | None = None
        touch: float | None = None
        if checked:
            touch_raw = sum(1 for c in checked if c) / len(checked)
            touch = scale(touch_raw, self.touch_bad, self.touch_good)

        parts = [p for p in (gesture, fidget, touch) if p is not None]
        score = stats.fmean(parts) if parts else None

        return HandsWindow(
            index=window.index,
            t_start_s=window.t_start_s,
            t_end_s=window.t_end_s,
            visibility=visibility,
            score=score,
            gesture=gesture,
            fidget=fidget,
            touch=touch,
            gesture_raw=gesture_raw,
            fidget_raw=fidget_raw,
            touch_raw=touch_raw,
            shoulder_width=shoulder_width,
        )

    def analyse(self, window: Window) -> AnalysisResult:
        """The interface fusion uses: a score and a visibility, nothing else."""
        detail = self.analyse_detail(window)
        return {"score": detail.score, "visibility": detail.visibility}
