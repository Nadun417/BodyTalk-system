"""The face channel: 468 face-mesh landmarks reduced to one score from 0 to 100.

Three measurements go into the face score:

  facing the camera     is the head turned away, or pointed roughly at the lens?
  expression liveliness is the face moving at all, or held completely still?
  head stability        is the head steady, or shifting around a lot?

Three things are deliberately left out:

  Smiling is measured elsewhere but never counts towards the score. Giving marks for
  smiling would effectively tell candidates to grin their way through an interview, which
  is bad advice. It is only ever used to point out a moment that went well, so it belongs
  with the feedback messages rather than with scoring.

  Blink rate was dropped from this version. Measuring it needs the detailed iris
  landmarks, which means turning on the refined 478-point face mesh, and the frame format
  this project settled on does not record those.

  Deciding what to actually say to the user happens later, in the feedback stage. This
  file produces the run of scores that those rules read; it does not word anything.

Everything here describes what can be seen and nothing more. A low liveliness score means
the face moved very little during that stretch of video. It does not mean the person was
bored, nervous or unenthusiastic, and nothing in this file should ever be read that way.

One quirk worth knowing: the face mesh gives no usable per-landmark visibility value, so
face visibility here is a detection rate instead. It is simply the fraction of frames in
the window where a face was found at all.
"""

from __future__ import annotations

import statistics as stats
from collections import deque
from dataclasses import dataclass

from .base import AnalysisResult, Analyser, Window, dist, presence_rate, scale, spread

# --- positions of the landmarks used, in the 468-point face mesh ----------------------
NOSE_TIP = 1
EYE_OUTER_RIGHT = 33
EYE_OUTER_LEFT = 263
LIP_INNER_UPPER = 13
LIP_INNER_LOWER = 14
BROW_RIGHT = 105  # the upper ridge of the eyebrow
BROW_LEFT = 334
MOUTH_CORNER_RIGHT = 61
MOUTH_CORNER_LEFT = 291
CHEEK_RIGHT = 234  # cheek to cheek is the face-width reference
CHEEK_LEFT = 454


@dataclass
class FaceWindow:
    """Everything worked out for one window, not just the final answer.

    `analyse()` only hands fusion the score and the visibility, because that is all fusion
    needs. This fuller version exists for tuning the thresholds later. To choose a sensible
    cut-off you have to be able to see the raw measurement sitting next to the score it
    produced, otherwise you are guessing.
    """

    index: int
    t_start_s: float
    t_end_s: float
    visibility: float
    score: float | None
    # the three sub-scores, 0 to 100, or None when there was not enough data
    facing: float | None
    liveliness: float | None
    stability: float | None
    # the raw measurements those sub-scores were calculated from
    asymmetry: float | None
    liveliness_raw: float | None
    stability_raw: float | None
    face_width: float | None
    #: mouth width over face width. Not scored. The smile rule compares it against the
    #: person's own median for the session, because resting mouth widths differ and a
    #: fixed threshold would simply favour some faces over others.
    mouth_width: float | None


class FaceAnalyser(Analyser):
    """Turns windows of face landmarks into a face score from 0 to 100.

    This class remembers things between windows, on purpose. Judging whether someone's
    expression is animated cannot be done from a single second of video, because anybody
    might hold a neutral face for a second while they think. So liveliness is measured
    across a rolling ten-second stretch, which means one instance handles one video and
    the windows have to be fed in the order they occurred.

    Every threshold below is a starting point that still has to be checked against real
    recordings. That is why they are all constructor arguments rather than fixed numbers
    buried in the code: tuning them should not mean editing the maths.
    """

    channel = "face"

    def __init__(
        self,
        aspect: float,
        # facing the camera: an asymmetry of 0.45 scores 0, and 0.10 scores 100
        facing_bad: float = 0.45,
        facing_good: float = 0.10,
        # liveliness: 0.005 scores 0, and 0.040 scores 100.
        # Calibrated 2 Sep 2026: a deliberately held-flat face measured 0.005, ordinary talking
        # 0.036 and animated talking 0.039. The old good end of 0.020 sat below ordinary talking,
        # so every real clip clamped at 100 and the measurement said nothing.
        liveliness_bad: float = 0.005,
        liveliness_good: float = 0.040,
        liveliness_span_s: float = 10.0,
        min_liveliness_samples: int = 12,  # roughly 2 seconds at 6 frames a second
        # head stability: a nose-tip spread of 0.14 scores 0, and 0.025 scores 100.
        # Calibrated 2 Sep 2026: deliberately shaking the head measured 0.115, while ordinary
        # animated talking measured 0.084. The old bad end of 0.08 sat below natural speech, so
        # simply talking expressively scored zero here, which is the opposite of the intent.
        stability_bad: float = 0.14,
        stability_good: float = 0.025,
    ) -> None:
        self.aspect = aspect
        self.facing_bad = facing_bad
        self.facing_good = facing_good
        self.liveliness_bad = liveliness_bad
        self.liveliness_good = liveliness_good
        self.liveliness_span_s = liveliness_span_s
        self.min_liveliness_samples = min_liveliness_samples
        self.stability_bad = stability_bad
        self.stability_good = stability_good

        #: the rolling ten seconds of (time, mouth openness, eyebrow height) readings
        self._recent: deque[tuple[float, float, float]] = deque()

    # --------------------------------------------------------- measurements per frame

    def _face_width(self, lm: list) -> float:
        """Distance from cheek to cheek, which every other face measurement divides by.

        Measuring against a part of the person rather than against pixels is what lets the
        same thresholds work whether they are sitting close to the camera or far back. A
        big face and a small face on screen give the same numbers once divided by this.
        """
        return dist(lm[CHEEK_RIGHT], lm[CHEEK_LEFT], self.aspect)

    def _asymmetry(self, lm: list) -> float:
        """How lopsided the eyes look around the nose. 0 means facing the camera.

        Turning the head shrinks the gap between the nose and one eye while widening the
        gap to the other, so comparing the two gaps says which way the head is pointed
        without needing to track the eyes themselves.

        Both gaps are horizontal, so the frame-shape correction would apply equally to
        each and cancels out when they are divided. That is why it is not applied here.
        """
        d_right = abs(lm[NOSE_TIP][0] - lm[EYE_OUTER_RIGHT][0])
        d_left = abs(lm[EYE_OUTER_LEFT][0] - lm[NOSE_TIP][0])
        total = d_right + d_left
        if total <= 0:
            return 0.0
        return abs(d_left - d_right) / total

    def _mouth_openness(self, lm: list, face_width: float) -> float:
        """Gap between the inner lips, divided by face width.

        This one is a vertical measurement divided by a horizontal one, so the frame-shape
        correction genuinely matters here, and it is already baked into `face_width`.
        """
        return abs(lm[LIP_INNER_UPPER][1] - lm[LIP_INNER_LOWER][1]) / face_width

    def _mouth_width(self, lm: list, face_width: float) -> float:
        """Corner-to-corner mouth width, divided by face width.

        Both measurements run across the face, so this one is unaffected by the frame
        shape either way, but it goes through the same corrected face width as everything
        else so that all the face numbers stay on one footing.
        """
        return dist(lm[MOUTH_CORNER_RIGHT], lm[MOUTH_CORNER_LEFT], self.aspect) / face_width

    def _eyebrow_height(self, lm: list, face_width: float) -> float:
        """Average gap from eyebrow to eye across both sides, divided by face width."""
        right = abs(lm[BROW_RIGHT][1] - lm[EYE_OUTER_RIGHT][1])
        left = abs(lm[BROW_LEFT][1] - lm[EYE_OUTER_LEFT][1])
        return (right + left) / (2.0 * face_width)

    # ---------------------------------------------------------- putting a window together

    def _nothing_seen(self, window: Window, visibility: float) -> "FaceWindow":
        """A window with no usable face in it.

        Reporting no score is the honest answer. A zero would read as poor body language
        when the truth is that nothing could be measured, so fusion leaves the channel out
        and the dashboard shows a gap rather than a number nobody can justify.
        """
        return FaceWindow(
            index=window.index,
            t_start_s=window.t_start_s,
            t_end_s=window.t_end_s,
            visibility=visibility,
            score=None,
            facing=None,
            liveliness=None,
            stability=None,
            asymmetry=None,
            liveliness_raw=None,
            stability_raw=None,
            face_width=None,
            mouth_width=None,
        )

    def analyse_detail(self, window: Window) -> FaceWindow:
        """Score one window and hand back the full working-out."""
        visibility = presence_rate(window, "face")
        detected = [f for f in window.frames if f["face"]["detected"]]

        if not detected:
            # No face was found anywhere in this window. Report no score rather than
            # making one up. Fusion will leave the channel out, and the dashboard shows
            # an honest gap in the timeline instead of a number nobody can justify.
            return self._nothing_seen(window, visibility)

        asymmetries: list[float] = []
        mouths: list[float] = []
        widths: list[float] = []
        noses: list[list[float]] = []

        for frame in detected:
            lm = frame["face"]["landmarks"]
            face_width = self._face_width(lm)
            if face_width <= 0:
                continue  # a broken detection, so skip this frame rather than divide by it

            widths.append(face_width)
            asymmetries.append(self._asymmetry(lm))
            mouths.append(self._mouth_width(lm, face_width))
            noses.append(lm[NOSE_TIP])
            self._recent.append(
                (
                    frame["tS"],
                    self._mouth_openness(lm, face_width),
                    self._eyebrow_height(lm, face_width),
                )
            )

        # Throw away readings that have fallen off the back of the ten-second span.
        cutoff = window.t_end_s - self.liveliness_span_s
        while self._recent and self._recent[0][0] < cutoff:
            self._recent.popleft()

        # A face was detected but every frame of it was unusable.
        if not widths:
            return self._nothing_seen(window, visibility)

        mean_width = stats.fmean(widths)

        # How square-on to the camera the head was.
        asymmetry = stats.fmean(asymmetries)
        facing = scale(asymmetry, self.facing_bad, self.facing_good)

        # How much the expression moved, measured over the rolling ten seconds.
        # Skipped entirely if too few readings have built up yet, which is the case at
        # the very start of a video.
        liveliness_raw: float | None = None
        liveliness: float | None = None
        if len(self._recent) >= self.min_liveliness_samples:
            liveliness_raw = stats.pstdev([m for _, m, _ in self._recent]) + stats.pstdev(
                [b for _, _, b in self._recent]
            )
            liveliness = scale(liveliness_raw, self.liveliness_bad, self.liveliness_good)

        # How much the head wandered within this one window. Needs at least two
        # positions before there is anything to compare.
        stability_raw: float | None = None
        stability: float | None = None
        if len(noses) >= 2:
            stability_raw = spread(noses, self.aspect) / mean_width
            stability = scale(stability_raw, self.stability_bad, self.stability_good)

        # Average whichever of the three could be worked out. They carry equal weight
        # because there is no evidence yet that any one of them matters more.
        parts = [p for p in (facing, liveliness, stability) if p is not None]
        score = stats.fmean(parts) if parts else None

        return FaceWindow(
            index=window.index,
            t_start_s=window.t_start_s,
            t_end_s=window.t_end_s,
            visibility=visibility,
            score=score,
            facing=facing,
            liveliness=liveliness,
            stability=stability,
            asymmetry=asymmetry,
            liveliness_raw=liveliness_raw,
            stability_raw=stability_raw,
            face_width=mean_width,
            mouth_width=stats.median(mouths) if mouths else None,
        )

    def analyse(self, window: Window) -> AnalysisResult:
        """The short version that fusion asks for: just the score and the visibility."""
        detail = self.analyse_detail(window)
        return {"score": detail.score, "visibility": detail.visibility}
