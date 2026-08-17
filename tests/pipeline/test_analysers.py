"""Unit tests for the shared analyser toolkit and the face channel analyser.

Windows are hand-crafted here rather than read from real footage: a synthetic face whose
geometry we control is the only way to assert "a perfectly symmetric face must score 100".
Calibration against real clips is a separate activity — it tunes thresholds, whereas these
tests pin down behaviour that must hold whatever the thresholds are.
"""

import math

from analysers import (
    FaceAnalyser,
    dist,
    presence_rate,
    scale,
    spread,
    window_frames,
)
from analysers.base import Window

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


def frame(t_s: float, face=None, left_hand: bool = False, right_hand: bool = False) -> dict:
    """One frame record in the shape the landmark cache stores."""
    return {
        "type": "frame",
        "frameIndex": int(t_s * 6),
        "tS": t_s,
        "face": {"detected": face is not None, "landmarks": face},
        "pose": {"detected": False, "landmarks": None},
        "leftHand": {"detected": left_hand, "landmarks": [] if left_hand else None},
        "rightHand": {"detected": right_hand, "landmarks": [] if right_hand else None},
    }


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
