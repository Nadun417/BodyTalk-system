"""Unit tests for the shared analyser toolkit and the face channel analyser.

Windows are hand-crafted here rather than read from real footage: a synthetic face whose
geometry we control is the only way to assert "a perfectly symmetric face must score 100".
Calibration against real clips is a separate activity — it tunes thresholds, whereas these
tests pin down behaviour that must hold whatever the thresholds are.
"""

import math

from analysers import (
    FaceAnalyser,
    HandsAnalyser,
    PoseAnalyser,
    dist,
    presence_rate,
    scale,
    spread,
    window_frames,
)
from analysers.base import Window
from analysers.hands import band_score

# --------------------------------------------------------------------------- test helpers

FACE_POINTS = 468


def build_face(
    aspect: float,
    nose_x: float = 0.0,
    lip_gap: float = 0.05,
    brow_gap: float = 0.10,
    face_width: float = 0.40,
) -> list:
    """A synthetic 468-point face, described in SQUARE units then converted.

    Coordinates are laid out as if the frame were square, then `x` is divided by `aspect`
    to produce what MediaPipe would actually report on a frame of that shape. That lets a
    test build *the same physical face* at two aspect ratios and assert the metrics agree —
    which is the whole point of the aspect correction.

    `nose_x` shifts the nose sideways from centre, which is how a turned head is simulated.
    """
    half = face_width / 2.0
    centre_x, centre_y = 0.5, 0.5

    def point(x_sq: float, y: float) -> list:
        return [x_sq / aspect, y, 0.0]

    lm = [[0.0, 0.0, 0.0] for _ in range(FACE_POINTS)]
    lm[1] = point(centre_x + nose_x, centre_y)  # nose tip
    lm[33] = point(centre_x - half, centre_y)  # right eye outer
    lm[263] = point(centre_x + half, centre_y)  # left eye outer
    lm[13] = point(centre_x, centre_y + 0.10)  # inner upper lip
    lm[14] = point(centre_x, centre_y + 0.10 + lip_gap)  # inner lower lip
    lm[105] = point(centre_x - half, centre_y - brow_gap)  # right brow
    lm[334] = point(centre_x + half, centre_y - brow_gap)  # left brow
    lm[234] = point(centre_x - half, centre_y)  # right cheek
    lm[454] = point(centre_x + half, centre_y)  # left cheek
    return lm


POSE_POINTS = 33


def build_pose(
    aspect: float,
    lean_x: float = 0.0,
    shoulder_drop: float = 0.0,
    centre_x: float = 0.5,
    shoulder_width: float = 0.40,
    neck_length: float = 0.20,
    visibility: float = 1.0,
    hip_visibility: float = 0.0,
    head_turn: float = 0.0,
) -> list:
    """A synthetic 33-point body, described in even units then converted.

    Same trick as the face builder: lay the body out as if the frame were square, then
    divide x by the aspect so it matches what MediaPipe would report on a frame of that
    shape. That lets a test build the same physical posture at two aspect ratios and check
    the measurements agree.

    `lean_x` slides the nose sideways from above the shoulders, which is how a lean is
    simulated. `shoulder_drop` lifts one shoulder above the other. `hip_visibility` is left
    at zero by default because a typical practice recording crops the hips out.
    """
    half = shoulder_width / 2.0
    shoulder_y = 0.6

    def point(x_even: float, y: float, vis: float) -> list:
        return [x_even / aspect, y, 0.0, vis]

    lm = [[0.0, 0.0, 0.0, 0.0] for _ in range(POSE_POINTS)]
    nose_x = centre_x + lean_x
    lm[0] = point(nose_x, shoulder_y - neck_length, visibility)  # nose
    # Eyes either side of the nose. `head_turn` shifts the nose between them, which is what
    # turning the head does: one nose-to-eye gap shrinks while the other grows.
    eye_half = 0.06
    lm[3] = point(nose_x + eye_half * (1 - head_turn), shoulder_y - neck_length, visibility)
    lm[6] = point(nose_x - eye_half * (1 + head_turn), shoulder_y - neck_length, visibility)
    lm[11] = point(centre_x + half, shoulder_y - shoulder_drop, visibility)  # left shoulder
    lm[12] = point(centre_x - half, shoulder_y, visibility)  # right shoulder
    lm[13] = point(centre_x + half, shoulder_y + 0.15, visibility)  # left elbow
    lm[14] = point(centre_x - half, shoulder_y + 0.15, visibility)  # right elbow
    lm[23] = point(centre_x + half * 0.7, shoulder_y + 0.35, hip_visibility)  # left hip
    lm[24] = point(centre_x - half * 0.7, shoulder_y + 0.35, hip_visibility)  # right hip
    return lm


def frame(
    t_s: float,
    face=None,
    pose=None,
    left_hand: bool = False,
    right_hand: bool = False,
) -> dict:
    """One frame record in the shape the landmark cache stores."""
    return {
        "type": "frame",
        "frameIndex": int(t_s * 6),
        "tS": t_s,
        "face": {"detected": face is not None, "landmarks": face},
        "pose": {"detected": pose is not None, "landmarks": pose},
        "leftHand": _hand_slot(left_hand),
        "rightHand": _hand_slot(right_hand),
    }


def _hand_slot(value) -> dict:
    """Accepts True/False for presence-only tests, or a real landmark list."""
    if value is None or value is False:
        return {"detected": False, "landmarks": None}
    if value is True:
        return {"detected": True, "landmarks": []}
    return {"detected": True, "landmarks": value}


HAND_POINTS = 21


def build_hand(aspect: float, wrist_x: float, wrist_y: float, tip_x=None, tip_y=None) -> list:
    """A synthetic 21-point hand. Fingertips sit on the wrist unless placed explicitly."""
    def point(x_even, y):
        return [x_even / aspect, y, 0.0]

    tip_x = wrist_x if tip_x is None else tip_x
    tip_y = wrist_y if tip_y is None else tip_y
    lm = [point(wrist_x, wrist_y) for _ in range(HAND_POINTS)]
    for i in (4, 8, 12, 16, 20):
        lm[i] = point(tip_x, tip_y)
    return lm


def one_window(frames: list) -> Window:
    return Window(index=0, t_start_s=0.0, t_end_s=1.0, frames=frames)


# ---------------------------------------------------------------------------- scale()


def test_scale_hits_both_endpoints():
    assert scale(0.45, 0.45, 0.10) == 0.0
    assert scale(0.10, 0.45, 0.10) == 100.0


def test_scale_clamps_beyond_the_endpoints():
    assert scale(0.90, 0.45, 0.10) == 0.0  # worse than "bad" is still 0, never negative
    assert scale(0.00, 0.45, 0.10) == 100.0  # better than "good" is still 100


def test_scale_works_when_larger_is_better():
    # liveliness: 0.002 is bad, 0.020 is good — the opposite direction to the above
    assert scale(0.002, 0.002, 0.020) == 0.0
    assert scale(0.020, 0.002, 0.020) == 100.0
    assert 49 < scale(0.011, 0.002, 0.020) < 51  # midpoint


# ------------------------------------------------------------------------- windowing


def test_window_frames_groups_by_second():
    frames = [frame(t / 6.0, build_face(1.0)) for t in range(18)]  # 3 s at 6 fps
    windows = list(window_frames(frames))
    assert [w.index for w in windows] == [0, 1, 2]
    assert [len(w.frames) for w in windows] == [6, 6, 6]
    assert windows[1].t_start_s == 1.0 and windows[1].t_end_s == 2.0


def test_window_frames_skips_gaps_rather_than_emitting_empty_windows():
    frames = [frame(0.0, build_face(1.0)), frame(5.0, build_face(1.0))]
    windows = list(window_frames(frames))
    assert [w.index for w in windows] == [0, 5]


# ------------------------------------------------------------------- presence / geometry


def test_presence_rate_counts_detected_frames():
    frames = [frame(0.0, build_face(1.0)), frame(0.2, None), frame(0.4, None), frame(0.6, None)]
    assert presence_rate(one_window(frames), "face") == 0.25


def test_presence_rate_averages_two_hand_keys_to_halves():
    frames = [
        frame(0.0, None, left_hand=True, right_hand=True),  # 1.0
        frame(0.2, None, left_hand=True, right_hand=False),  # 0.5
        frame(0.4, None, left_hand=False, right_hand=False),  # 0.0
    ]
    assert abs(presence_rate(one_window(frames), "leftHand", "rightHand") - 0.5) < 1e-9


def test_dist_undoes_the_per_axis_normalisation():
    # A horizontal span of 0.5 normalised units on a 2:1 frame is physically twice as
    # long as the same number of vertical units.
    assert abs(dist([0.0, 0.0], [0.5, 0.0], aspect=2.0) - 1.0) < 1e-9
    assert abs(dist([0.0, 0.0], [0.0, 0.5], aspect=2.0) - 0.5) < 1e-9


def test_spread_is_zero_for_a_stationary_point():
    assert spread([[0.3, 0.3], [0.3, 0.3], [0.3, 0.3]], aspect=1.5) == 0.0


# ------------------------------------------------------------------------ FaceAnalyser


def test_undetected_face_yields_no_score_not_a_zero():
    """A channel that was never seen must report None, so fusion can exclude it.

    Scoring 0 would be a lie — it would say "bad body language" when the truth is
    "we could not see".
    """
    analyser = FaceAnalyser(aspect=1.78)
    result = analyser.analyse(one_window([frame(0.0, None), frame(0.2, None)]))
    assert result["score"] is None
    assert result["visibility"] == 0.0


def test_symmetric_face_scores_full_marks_on_facing_camera():
    analyser = FaceAnalyser(aspect=1.78)
    frames = [frame(t / 6.0, build_face(1.78, nose_x=0.0)) for t in range(6)]
    detail = analyser.analyse_detail(one_window(frames))
    assert detail.asymmetry < 1e-9
    assert detail.facing == 100.0
    assert detail.visibility == 1.0


def test_turned_head_scores_low_on_facing_camera():
    analyser = FaceAnalyser(aspect=1.78)
    # Nose shifted most of the way to one eye — a strongly turned head.
    frames = [frame(t / 6.0, build_face(1.78, nose_x=0.16)) for t in range(6)]
    detail = analyser.analyse_detail(one_window(frames))
    assert detail.asymmetry > 0.4
    assert detail.facing < 20.0


def test_still_head_scores_full_marks_on_stability():
    analyser = FaceAnalyser(aspect=1.78)
    frames = [frame(t / 6.0, build_face(1.78)) for t in range(6)]
    detail = analyser.analyse_detail(one_window(frames))
    assert detail.stability_raw == 0.0
    assert detail.stability == 100.0


def test_facing_metric_is_aspect_invariant():
    """The facing measure divides one sideways distance by another, so the frame shape
    should cancel out of it entirely. This checks that it genuinely does."""
    frames_wide = [frame(t / 6.0, build_face(1.78, nose_x=0.10)) for t in range(6)]
    frames_square = [frame(t / 6.0, build_face(1.00, nose_x=0.10)) for t in range(6)]
    wide = FaceAnalyser(aspect=1.78).analyse_detail(one_window(frames_wide))
    square = FaceAnalyser(aspect=1.00).analyse_detail(one_window(frames_square))
    assert abs(wide.asymmetry - square.asymmetry) < 1e-9


def test_mouth_openness_is_aspect_invariant_after_correction():
    """Regression test for the bug that made this correction necessary.

    The same physical face filmed on a 16:9 frame and on a square one must produce the same
    mouth-openness measurement. Before the correction these differed by the aspect ratio,
    so any threshold calibrated on one clip was wrong on the other.
    """
    analysers = []
    for aspect in (1.00, 1.78):
        analyser = FaceAnalyser(aspect=aspect)
        frames = [frame(t / 6.0, build_face(aspect, lip_gap=0.05)) for t in range(6)]
        analyser.analyse_detail(one_window(frames))
        # the rolling buffer holds the per-frame mouth-openness values
        analysers.append(analyser._recent[0][1])
    assert abs(analysers[0] - analysers[1]) < 1e-9


def test_face_width_is_measured_in_square_units():
    analyser = FaceAnalyser(aspect=1.78)
    frames = [frame(0.0, build_face(1.78, face_width=0.40))]
    detail = analyser.analyse_detail(one_window(frames))
    assert abs(detail.face_width - 0.40) < 1e-9


def test_liveliness_needs_enough_samples_before_it_reports():
    """Early in a video there is not yet ten seconds of history, so liveliness holds back.

    It must abstain rather than report 0 — a still face for the first second is not
    evidence of a flat expression, and scoring it as such would be unfair.
    """
    analyser = FaceAnalyser(aspect=1.78, min_liveliness_samples=12)
    frames = [frame(t / 6.0, build_face(1.78)) for t in range(6)]  # only 6 samples
    detail = analyser.analyse_detail(one_window(frames))
    assert detail.liveliness is None
    # ...and the channel score is still produced from the metrics that *are* available
    assert detail.score is not None


def test_motionless_face_over_ten_seconds_scores_zero_liveliness():
    analyser = FaceAnalyser(aspect=1.78)
    frames = [frame(t / 6.0, build_face(1.78)) for t in range(60)]  # 10 s, identical faces
    detail = None
    for window in window_frames(frames):
        detail = analyser.analyse_detail(window)
    assert detail.liveliness_raw == 0.0
    assert detail.liveliness == 0.0


def test_moving_face_scores_higher_liveliness_than_a_still_one():
    still = FaceAnalyser(aspect=1.78)
    lively = FaceAnalyser(aspect=1.78)

    still_frames = [frame(t / 6.0, build_face(1.78, lip_gap=0.05)) for t in range(60)]
    lively_frames = [
        frame(
            t / 6.0,
            build_face(1.78, lip_gap=0.05 + 0.04 * math.sin(t), brow_gap=0.10 + 0.02 * math.cos(t)),
        )
        for t in range(60)
    ]

    still_detail = lively_detail = None
    for window in window_frames(still_frames):
        still_detail = still.analyse_detail(window)
    for window in window_frames(lively_frames):
        lively_detail = lively.analyse_detail(window)

    assert lively_detail.liveliness_raw > still_detail.liveliness_raw
    assert lively_detail.liveliness > still_detail.liveliness


def test_score_is_the_mean_of_available_sub_scores():
    analyser = FaceAnalyser(aspect=1.78)
    frames = [frame(t / 6.0, build_face(1.78)) for t in range(6)]
    detail = analyser.analyse_detail(one_window(frames))
    parts = [p for p in (detail.facing, detail.liveliness, detail.stability) if p is not None]
    assert abs(detail.score - sum(parts) / len(parts)) < 1e-9


# ------------------------------------------------------------------------ PoseAnalyser


def pose_window(frames: list) -> Window:
    return Window(index=0, t_start_s=0.0, t_end_s=1.0, frames=frames)


def test_undetected_body_yields_no_score_not_a_zero():
    """Same rule as the face channel: nothing seen means no score, never a zero.

    A zero would read as poor posture when the truth is that the body was not in shot.
    """
    analyser = PoseAnalyser(aspect=1.78)
    result = analyser.analyse(pose_window([frame(0.0), frame(0.2)]))
    assert result["score"] is None
    assert result["visibility"] == 0.0


def test_upright_still_body_scores_full_marks():
    analyser = PoseAnalyser(aspect=1.78)
    frames = [frame(t / 6.0, pose=build_pose(1.78)) for t in range(6)]
    detail = analyser.analyse_detail(pose_window(frames))
    assert detail.lean_degrees < 1e-9  # nose directly above the shoulder midpoint
    assert detail.uprightness == 100.0
    assert detail.levelness == 100.0  # shoulders exactly level
    assert detail.sway == 100.0  # body did not move at all
    assert detail.score == 100.0


def test_leaning_body_scores_low_on_uprightness():
    analyser = PoseAnalyser(aspect=1.78)
    # Nose pushed well to one side of the shoulder midpoint over a short neck.
    frames = [frame(t / 6.0, pose=build_pose(1.78, lean_x=0.15, neck_length=0.20)) for t in range(6)]
    detail = analyser.analyse_detail(pose_window(frames))
    assert detail.lean_degrees > 25.0
    assert detail.uprightness == 0.0


def test_uneven_shoulders_score_low_on_levelness():
    analyser = PoseAnalyser(aspect=1.78)
    # One shoulder a fifth of a shoulder-width higher than the other.
    frames = [
        frame(t / 6.0, pose=build_pose(1.78, shoulder_drop=0.08, shoulder_width=0.40))
        for t in range(6)
    ]
    detail = analyser.analyse_detail(pose_window(frames))
    assert detail.levelness_raw > 0.18
    assert detail.levelness == 0.0


def test_body_drifting_sideways_scores_low_on_sway():
    analyser = PoseAnalyser(aspect=1.78)
    # The whole body slides across the frame during the window.
    frames = [
        frame(t / 6.0, pose=build_pose(1.78, centre_x=0.5 + 0.02 * t)) for t in range(6)
    ]
    detail = analyser.analyse_detail(pose_window(frames))
    assert detail.sway_raw > 0.06
    assert detail.sway == 0.0


def test_lean_angle_is_the_same_whatever_shape_the_video_is():
    """A given physical lean has to read as the same number of degrees on any frame shape.

    Angles are the measurement most easily ruined by the per-axis normalisation, because a
    sideways offset and an upward offset are compared directly against each other.
    """
    wide = PoseAnalyser(aspect=1.78).analyse_detail(
        pose_window([frame(0.0, pose=build_pose(1.78, lean_x=0.05))])
    )
    squarish = PoseAnalyser(aspect=1.00).analyse_detail(
        pose_window([frame(0.0, pose=build_pose(1.00, lean_x=0.05))])
    )
    assert abs(wide.lean_degrees - squarish.lean_degrees) < 1e-9


def test_shoulder_width_is_measured_in_even_units():
    analyser = PoseAnalyser(aspect=1.78)
    frames = [frame(0.0, pose=build_pose(1.78, shoulder_width=0.40))]
    detail = analyser.analyse_detail(pose_window(frames))
    assert abs(detail.shoulder_width - 0.40) < 1e-9


def test_visibility_is_the_mean_over_the_chosen_landmarks():
    analyser = PoseAnalyser(aspect=1.78)
    frames = [frame(0.0, pose=build_pose(1.78, visibility=0.6))]
    detail = analyser.analyse_detail(pose_window(frames))
    assert abs(detail.visibility - 0.6) < 1e-9


def test_visibility_counts_frames_where_the_body_vanished():
    """Half the window missing the body should read as half seen, not fully seen.

    Averaging only over the detected frames would quietly hide the gap, and hiding gaps is
    the opposite of what the visibility figure exists to do.
    """
    analyser = PoseAnalyser(aspect=1.78)
    frames = [
        frame(0.0, pose=build_pose(1.78, visibility=1.0)),
        frame(0.2, pose=build_pose(1.78, visibility=1.0)),
        frame(0.4),
        frame(0.6),
    ]
    detail = analyser.analyse_detail(pose_window(frames))
    assert abs(detail.visibility - 0.5) < 1e-9


def test_cropped_hips_are_simply_not_used():
    analyser = PoseAnalyser(aspect=1.78)
    frames = [frame(0.0, pose=build_pose(1.78, hip_visibility=0.0))]
    detail = analyser.analyse_detail(pose_window(frames))
    assert detail.used_hips is False
    assert detail.uprightness is not None  # still scored, from the neck line alone


def test_visible_hips_are_used_and_can_only_make_the_lean_worse():
    """With hips in shot the worse of the two lean readings wins.

    Someone can hold their neck straight while their whole torso tips over, so the torso
    line has to be able to override a flattering neck reading — never the other way round.
    """
    upright_neck = build_pose(1.78, lean_x=0.0, hip_visibility=0.9)
    # Slide the shoulders sideways relative to the hips, leaving the neck vertical.
    for index in (11, 12, 0):
        upright_neck[index][0] += 0.10

    analyser = PoseAnalyser(aspect=1.78)
    detail = analyser.analyse_detail(pose_window([frame(0.0, pose=upright_neck)]))
    assert detail.used_hips is True
    assert detail.lean_degrees > 0.0


def test_pose_score_is_the_mean_of_available_sub_scores():
    analyser = PoseAnalyser(aspect=1.78)
    frames = [frame(t / 6.0, pose=build_pose(1.78, lean_x=0.03, shoulder_drop=0.02)) for t in range(6)]
    detail = analyser.analyse_detail(pose_window(frames))
    parts = [p for p in (detail.uprightness, detail.levelness, detail.sway) if p is not None]
    assert abs(detail.score - sum(parts) / len(parts)) < 1e-9


# ----------------------------------------------------------------------- HandsAnalyser


def hand_frames(aspect, positions, face=None, pose=None, tips=None):
    """Frames with one moving hand, plus the pose and face it needs for scale."""
    out = []
    for i, (x, y) in enumerate(positions):
        tip = tips[i] if tips else (None, None)
        out.append(
            frame(
                i / 6.0,
                face=face if face is not None else build_face(aspect),
                pose=pose if pose is not None else build_pose(aspect),
                left_hand=build_hand(aspect, x, y, tip[0], tip[1]),
            )
        )
    return out


def test_band_score_rewards_the_middle_and_penalises_both_extremes():
    assert band_score(0.3, 0.05, 0.15, 0.7, 1.2) == 100.0  # comfortably inside
    assert band_score(0.01, 0.05, 0.15, 0.7, 1.2) == 40.0  # far too still
    assert band_score(2.0, 0.05, 0.15, 0.7, 1.2) == 40.0  # far too much
    # and it slides rather than stepping between those
    assert 40.0 < band_score(0.1, 0.05, 0.15, 0.7, 1.2) < 100.0
    assert 40.0 < band_score(0.9, 0.05, 0.15, 0.7, 1.2) < 100.0


def test_hands_out_of_frame_yields_no_score_not_a_zero():
    """The hands channel abstains when the hands are not in shot.

    This is the case the whole adaptive-fusion idea exists for: no score, visibility zero,
    so fusion drops the channel instead of reading absence as bad gesturing.
    """
    analyser = HandsAnalyser(aspect=1.78)
    frames = [frame(0.0, pose=build_pose(1.78)), frame(0.2, pose=build_pose(1.78))]
    result = analyser.analyse(one_window(frames))
    assert result["score"] is None
    assert result["visibility"] == 0.0


def test_visibility_is_a_half_when_only_one_hand_is_seen():
    analyser = HandsAnalyser(aspect=1.78)
    frames = [frame(0.0, pose=build_pose(1.78), left_hand=build_hand(1.78, 0.4, 0.7))]
    detail = analyser.analyse_detail(one_window(frames))
    assert detail.visibility == 0.5


def test_motionless_hands_are_scored_as_too_still():
    analyser = HandsAnalyser(aspect=1.78)
    frames = hand_frames(1.78, [(0.4, 0.7)] * 6)
    detail = analyser.analyse_detail(one_window(frames))
    assert detail.gesture_raw < 0.05
    assert detail.gesture == 40.0  # the floor, not zero


def test_wildly_moving_hands_are_also_penalised():
    analyser = HandsAnalyser(aspect=1.78)
    # A wrist crossing a large distance every frame.
    frames = hand_frames(1.78, [(0.2 + 0.25 * (i % 2), 0.7) for i in range(6)])
    detail = analyser.analyse_detail(one_window(frames))
    assert detail.gesture_raw > 0.85
    assert detail.gesture == 40.0


def test_jitter_on_a_still_hand_is_not_counted_as_fidgeting():
    """Regression test. A motionless wrist wobbles by a pixel or two every frame, and
    every wobble reverses direction, so without a noise floor a perfectly still hand
    measured as the most fidgety thing in the corpus."""
    analyser = HandsAnalyser(aspect=1.78)
    jitter = [(0.4 + 0.0005 * (1 if i % 2 else -1), 0.7) for i in range(12)]
    detail = analyser.analyse_detail(one_window(hand_frames(1.78, jitter)))
    assert detail.fidget_raw == 0.0
    assert detail.fidget == 100.0


def test_real_small_reversals_are_counted_as_fidgeting():
    analyser = HandsAnalyser(aspect=1.78)
    # Steps of 0.02 across: above the 0.004 noise floor, below the 0.048 gesture cutoff
    # (both derived from the 0.40 shoulder width of the synthetic body).
    shuffle = [(0.4 + 0.01 * (1 if i % 2 else -1), 0.7) for i in range(12)]
    detail = analyser.analyse_detail(one_window(hand_frames(1.78, shuffle)))
    assert detail.fidget_raw > 0.0
    assert detail.fidget < 100.0


def test_fingertip_at_the_nose_registers_as_hand_to_face():
    analyser = HandsAnalyser(aspect=1.78)
    face = build_face(1.78)
    nose = face[1]
    frames = hand_frames(
        1.78,
        [(0.4, 0.7)] * 6,
        face=face,
        tips=[(nose[0] * 1.78, nose[1])] * 6,  # fingertips placed on the nose
    )
    detail = analyser.analyse_detail(one_window(frames))
    assert detail.touch_raw == 1.0
    assert detail.touch == 0.0


def test_hand_well_away_from_the_face_does_not_register():
    analyser = HandsAnalyser(aspect=1.78)
    frames = hand_frames(1.78, [(0.4, 0.95)] * 6, tips=[(0.4, 0.95)] * 6)
    detail = analyser.analyse_detail(one_window(frames))
    assert detail.touch_raw == 0.0
    assert detail.touch == 100.0


def test_hand_to_face_abstains_when_the_face_was_not_detected():
    """Not checking and checking-and-finding-nothing are different answers.

    Merging them would turn missing evidence into a clean bill of health.
    """
    analyser = HandsAnalyser(aspect=1.78)
    frames = [
        frame(i / 6.0, face=None, pose=build_pose(1.78), left_hand=build_hand(1.78, 0.4, 0.7))
        for i in range(6)
    ]
    detail = analyser.analyse_detail(one_window(frames))
    assert detail.touch_raw is None
    assert detail.touch is None
    assert detail.score is not None  # still scored from the measurements it could make


def test_gesture_speed_is_the_same_whatever_shape_the_video_is():
    positions = [(0.30 + 0.04 * i, 0.7) for i in range(6)]
    wide = HandsAnalyser(aspect=1.78).analyse_detail(one_window(hand_frames(1.78, positions)))
    squarish = HandsAnalyser(aspect=1.00).analyse_detail(one_window(hand_frames(1.00, positions)))
    assert abs(wide.gesture_raw - squarish.gesture_raw) < 1e-9


def test_head_turn_reads_zero_when_facing_the_camera():
    analyser = PoseAnalyser(aspect=1.78)
    detail = analyser.analyse_detail(pose_window([frame(0.0, pose=build_pose(1.78))]))
    assert detail.head_turn < 1e-9


def test_a_turned_head_withholds_the_lean_score_but_keeps_the_others():
    """The lean is taken from the nose, so a turned head and a leaning body produce the
    same reading and cannot be told apart. When the head is turned the lean is therefore
    not reported, rather than reported wrongly. Levelness and sway are unaffected, because
    neither of them uses the nose.
    """
    turned = build_pose(1.78, lean_x=0.15, head_turn=0.8)
    detail = PoseAnalyser(aspect=1.78).analyse_detail(pose_window([frame(0.0, pose=turned)]))
    assert detail.head_turn > 0.30
    assert detail.uprightness is None
    assert detail.lean_degrees is not None  # still reported, so the reason stays visible
    assert detail.levelness is not None
    assert detail.score is not None  # scored from the measurements that remain valid


def test_a_leaning_body_still_scores_when_the_head_faces_the_camera():
    """The gate must not silence real posture problems, only ambiguous ones."""
    leaning = [frame(t / 6.0, pose=build_pose(1.78, lean_x=0.15, head_turn=0.0)) for t in range(6)]
    detail = PoseAnalyser(aspect=1.78).analyse_detail(pose_window(leaning))
    assert detail.head_turn < 0.30
    assert detail.uprightness == 0.0
