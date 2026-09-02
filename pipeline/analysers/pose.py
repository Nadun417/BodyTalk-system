"""The body posture channel: 33 body keypoints reduced to one score from 0 to 100.

MediaPipe reports 33 body keypoints, and unlike the face and hands it gives a real
visibility number for each one, so this is the only channel that can measure how well it
was seen directly rather than falling back on how often it was detected.

Three measurements go into the posture score:

  posture uprightness   the angle the head and shoulders lean away from vertical
  shoulder levelness    how much higher one shoulder sits than the other
  body sway             how much the upper body drifts from side to side

Only the upper body is used. Practice videos are usually recorded on a laptop or phone
propped up on a desk, which crops everything below the chest, so anything depending on
hip position would fail on most real recordings. Hips are read when they happen to be in
shot, because they make the lean measurement more reliable, but nothing here requires them.

Everything measured is a position or an angle. A low posture score means the shoulders and
head were not where an upright, settled sitting position would put them, for however long
the window covers. It says nothing about why, and nothing about the person.

Deciding what to actually tell the user happens later, in the feedback stage. This file
produces the run of scores those rules read; it does not word anything.
"""

from __future__ import annotations

import math
import statistics as stats
from dataclasses import dataclass

from .base import AnalysisResult, Analyser, Window, dist, scale, square

# --- positions of the landmarks used, in the 33-point body model ----------------------
NOSE = 0
EYE_OUTER_LEFT = 3
EYE_OUTER_RIGHT = 6
SHOULDER_LEFT = 11
SHOULDER_RIGHT = 12
ELBOW_LEFT = 13
ELBOW_RIGHT = 14
HIP_LEFT = 23
HIP_RIGHT = 24

#: Which landmarks count towards how well this channel was seen.
#:
#: Deliberately not all 33. Legs and feet are almost never in frame in a seated interview
#: recording, and MediaPipe correctly reports that it cannot see them, so including them
#: would drag the number down for a reason that has nothing to do with the person's posture.
#: Averaging over the upper body instead keeps the figure about whether the part being
#: judged was actually visible.
#:
#: The elbows are in the set as an indicator of whether the upper body is framed widely
#: enough. Measuring against the cached clips showed they are often cropped out on
#: head-and-shoulders framing and pull this figure down noticeably, so narrowing the set to
#: just the nose and shoulders is the likely outcome once there is footage to tune against.
#: That is why the set is a constructor argument and not a fixed list.
VISIBILITY_LANDMARKS = (NOSE, SHOULDER_LEFT, SHOULDER_RIGHT, ELBOW_LEFT, ELBOW_RIGHT)


@dataclass
class PoseWindow:
    """Everything worked out for one window, not just the final answer.

    `analyse()` only hands fusion the score and the visibility, because that is all fusion
    needs. This fuller version exists for tuning the thresholds later, when being able to
    see the raw measurement next to the score it produced is the difference between
    choosing a cut-off and guessing at one.
    """

    index: int
    t_start_s: float
    t_end_s: float
    visibility: float
    score: float | None
    # the three sub-scores, 0 to 100, or None when there was not enough data
    uprightness: float | None
    levelness: float | None
    sway: float | None
    # the raw measurements those sub-scores were calculated from
    lean_degrees: float | None
    levelness_raw: float | None
    sway_raw: float | None
    shoulder_width: float | None
    #: how far the head was turned away from the camera, 0 when facing it
    head_turn: float | None
    #: whether the hips happened to be visible enough to help with the lean measurement
    used_hips: bool


class PoseAnalyser(Analyser):
    """Turns windows of body landmarks into a posture score from 0 to 100.

    Unlike the face analyser this one holds no state between windows: every measurement it
    makes is answerable from the second of video in front of it. Sway needs several frames,
    but they all sit inside the same window.

    Every threshold below is a starting point that still has to be checked against real
    recordings, which is why they are constructor arguments rather than fixed numbers
    buried in the maths.
    """

    channel = "pose"

    def __init__(
        self,
        aspect: float,
        # uprightness: leaning 25 degrees off vertical scores 0, 6 degrees scores 100
        upright_bad_degrees: float = 25.0,
        upright_good_degrees: float = 6.0,
        # levelness: a shoulder height difference of 0.18 of shoulder width scores 0
        levelness_bad: float = 0.18,
        levelness_good: float = 0.03,
        # sway: drifting 0.06 of a shoulder width within the window scores 0
        sway_bad: float = 0.06,
        sway_good: float = 0.008,
        visibility_landmarks: tuple[int, ...] = VISIBILITY_LANDMARKS,
        hip_visibility_min: float = 0.5,
        # Above this much head turn, the lean reading is not a posture measurement and is
        # withheld. Chosen from the calibration footage: at 0.30 it covers 100 % of the
        # deliberately turned-head segment, 0 % of the deliberate sideways torso lean, and
        # under 1 % of ordinary talking.
        head_turn_max: float = 0.30,
    ) -> None:
        self.aspect = aspect
        self.upright_bad_degrees = upright_bad_degrees
        self.upright_good_degrees = upright_good_degrees
        self.levelness_bad = levelness_bad
        self.levelness_good = levelness_good
        self.sway_bad = sway_bad
        self.sway_good = sway_good
        self.visibility_landmarks = visibility_landmarks
        self.hip_visibility_min = hip_visibility_min
        self.head_turn_max = head_turn_max

    # --------------------------------------------------------- measurements per frame

    def _visibility(self, lm: list) -> float:
        """How clearly the upper body was seen in this frame, from 0 to 1.

        Body landmarks carry a fourth number alongside their position, which is MediaPipe's
        own confidence that the point is actually visible rather than guessed at. Averaging
        that across the chosen landmarks is what makes this the one channel with a first-hand
        answer to "could we see it?" instead of an inferred one.
        """
        return stats.fmean([lm[i][3] for i in self.visibility_landmarks])

    def _head_turn(self, lm: list) -> float:
        """How far the head is turned away from the camera. 0 means facing it.

        Compares the gap from the nose to each eye. Facing the camera the two are equal;
        turning the head shrinks one and grows the other. Both gaps run across the face, so
        the frame-shape correction cancels in the ratio and is not applied.

        This exists because the lean measurement below is taken from the nose, and a turned
        head moves the nose just as a leaning body does. The two are indistinguishable in
        that measurement: a deliberately turned head reads 25.3 degrees of lean, and a
        deliberate sideways torso lean reads 24.0. So the lean has to be withheld when the
        head is turned, and this is how that condition is recognised.

        Measured from the pose model's own eye landmarks rather than the face mesh, so the
        pose channel stays independent of the face channel.
        """
        d_left = abs(lm[EYE_OUTER_LEFT][0] - lm[NOSE][0])
        d_right = abs(lm[NOSE][0] - lm[EYE_OUTER_RIGHT][0])
        total = d_left + d_right
        if total <= 0:
            return 0.0
        return abs(d_left - d_right) / total

    def _shoulder_width(self, lm: list) -> float:
        """Distance from shoulder to shoulder, which the other measurements divide by.

        Measuring against the person rather than against the frame is what lets the same
        thresholds work whether they are sitting close to the camera or well back from it.
        """
        return dist(lm[SHOULDER_LEFT], lm[SHOULDER_RIGHT], self.aspect)

    def _shoulder_midpoint(self, lm: list) -> tuple[float, float]:
        """The point halfway between the shoulders, in aspect-corrected units."""
        left = square(lm[SHOULDER_LEFT], self.aspect)
        right = square(lm[SHOULDER_RIGHT], self.aspect)
        return ((left[0] + right[0]) / 2.0, (left[1] + right[1]) / 2.0)

    def _angle_from_vertical(self, base: tuple[float, float], tip: tuple[float, float]) -> float:
        """How far the line from `base` up to `tip` tilts away from straight up, in degrees.

        Zero means perfectly vertical. The measurement has to happen in aspect-corrected
        units, because an angle read straight off normalised coordinates would be squashed
        or stretched depending on the shape of the video, and the same lean would then read
        as a different number of degrees on a widescreen clip than on a squarer one.
        """
        dx = tip[0] - base[0]
        dy = tip[1] - base[1]
        if dx == 0.0 and dy == 0.0:
            return 0.0
        # Vertical is the y direction, so the angle from vertical compares sideways
        # movement against movement along y. Absolute values because leaning left and
        # leaning right are equally far from upright, and because y grows downwards.
        return math.degrees(math.atan2(abs(dx), abs(dy)))

    def _lean_degrees(self, lm: list) -> tuple[float, bool]:
        """How far the upper body tilts off vertical, and whether the hips helped decide.

        The reliable measurement is the neck line, from the midpoint of the shoulders up to
        the nose. Slouching or craning forward tips the head off the shoulder line, and that
        shows up as this angle opening out.

        When the hips are in shot they give a second line, from the hip midpoint up to the
        shoulder midpoint, which catches a whole upper body leaning while the neck stays
        straight. The worse of the two angles is used, because either kind of lean is worth
        pointing out and neither should be able to hide behind the other.
        """
        mid_shoulder = self._shoulder_midpoint(lm)
        nose = square(lm[NOSE], self.aspect)
        neck_angle = self._angle_from_vertical(mid_shoulder, nose)

        hips_visible = (
            lm[HIP_LEFT][3] >= self.hip_visibility_min
            and lm[HIP_RIGHT][3] >= self.hip_visibility_min
        )
        if not hips_visible:
            return neck_angle, False

        left_hip = square(lm[HIP_LEFT], self.aspect)
        right_hip = square(lm[HIP_RIGHT], self.aspect)
        mid_hip = ((left_hip[0] + right_hip[0]) / 2.0, (left_hip[1] + right_hip[1]) / 2.0)
        torso_angle = self._angle_from_vertical(mid_hip, mid_shoulder)

        return max(neck_angle, torso_angle), True

    def _levelness_raw(self, lm: list, shoulder_width: float) -> float:
        """Height difference between the shoulders, as a fraction of shoulder width.

        A vertical measurement divided by a horizontal one, so the frame-shape correction
        genuinely matters here, and it is already baked into the shoulder width.
        """
        drop = abs(lm[SHOULDER_LEFT][1] - lm[SHOULDER_RIGHT][1])
        return drop / shoulder_width

    # ---------------------------------------------------- putting a window together

    def _nothing_seen(self, window: Window, visibility: float) -> PoseWindow:
        """A window with no usable body landmarks.

        Reporting no score is the honest answer, and it matters: a zero would claim poor
        posture when the truth is that nothing could be measured. Fusion leaves the channel
        out entirely, and the dashboard shows a gap rather than a made-up number.
        """
        return PoseWindow(
            index=window.index,
            t_start_s=window.t_start_s,
            t_end_s=window.t_end_s,
            visibility=visibility,
            score=None,
            uprightness=None,
            levelness=None,
            sway=None,
            lean_degrees=None,
            levelness_raw=None,
            sway_raw=None,
            shoulder_width=None,
            head_turn=None,
            used_hips=False,
        )

    def analyse_detail(self, window: Window) -> PoseWindow:
        """Score one window and hand back the full working-out."""
        detected = [f for f in window.frames if f["pose"]["detected"]]
        if not detected:
            return self._nothing_seen(window, 0.0)

        # Visibility is averaged over every frame in the window, not only the detected
        # ones, so a window where the body vanished halfway through reports as half seen.
        per_frame_visibility = [
            self._visibility(f["pose"]["landmarks"]) if f["pose"]["detected"] else 0.0
            for f in window.frames
        ]
        visibility = stats.fmean(per_frame_visibility)

        leans: list[float] = []
        levelnesses: list[float] = []
        widths: list[float] = []
        midpoint_xs: list[float] = []
        head_turns: list[float] = []
        used_hips = False

        for frame in detected:
            lm = frame["pose"]["landmarks"]
            shoulder_width = self._shoulder_width(lm)
            if shoulder_width <= 0:
                continue  # shoulders on top of each other means nothing can be divided

            widths.append(shoulder_width)
            lean, hips = self._lean_degrees(lm)
            leans.append(lean)
            used_hips = used_hips or hips
            levelnesses.append(self._levelness_raw(lm, shoulder_width))
            midpoint_xs.append(self._shoulder_midpoint(lm)[0])
            head_turns.append(self._head_turn(lm))

        if not widths:
            return self._nothing_seen(window, visibility)

        mean_width = stats.fmean(widths)

        lean_degrees = stats.fmean(leans)
        head_turn = stats.median(head_turns) if head_turns else 0.0

        # With the head turned, the line from the shoulders to the nose says where the head
        # is pointing, not how the body is sitting, so no posture claim can be made from it.
        # Reporting nothing is the honest answer: the alternative is telling somebody they
        # slouched because they looked at their notes, and a user who is told that once
        # stops believing the rest. The lean is still reported for transparency; only the
        # score derived from it is withheld.
        if head_turn > self.head_turn_max:
            uprightness = None
        else:
            uprightness = scale(lean_degrees, self.upright_bad_degrees, self.upright_good_degrees)

        levelness_raw = stats.fmean(levelnesses)
        levelness = scale(levelness_raw, self.levelness_bad, self.levelness_good)

        # Sway is side-to-side drift only. Someone shifting left and right in their seat is
        # restless in a way a viewer notices; the same amount of up-and-down movement is
        # usually just breathing or gesturing, so the vertical direction is left out.
        sway_raw: float | None = None
        sway: float | None = None
        if len(midpoint_xs) >= 2:
            sway_raw = stats.pstdev(midpoint_xs) / mean_width
            sway = scale(sway_raw, self.sway_bad, self.sway_good)

        parts = [p for p in (uprightness, levelness, sway) if p is not None]
        score = stats.fmean(parts) if parts else None

        return PoseWindow(
            index=window.index,
            t_start_s=window.t_start_s,
            t_end_s=window.t_end_s,
            visibility=visibility,
            score=score,
            uprightness=uprightness,
            levelness=levelness,
            sway=sway,
            lean_degrees=lean_degrees,
            levelness_raw=levelness_raw,
            sway_raw=sway_raw,
            shoulder_width=mean_width,
            head_turn=head_turn,
            used_hips=used_hips,
        )

    def analyse(self, window: Window) -> AnalysisResult:
        """The interface fusion uses: a score and a visibility, nothing else.

        Note that a very low visibility still comes back with a score attached. Deciding
        that a channel was seen too poorly to be worth listening to is fusion's job, not
        this analyser's, and keeping that decision in one place is what allows the adaptive
        and fixed-weight strategies to be swapped without touching any of this.
        """
        detail = self.analyse_detail(window)
        return {"score": detail.score, "visibility": detail.visibility}
