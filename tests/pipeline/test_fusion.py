"""Tests for the two ways of combining channel scores.

These matter more than most tests in the project. The comparison between adaptive and fixed
weighting is the thing being investigated, so a mistake in either one would not show up as a
crash. It would show up as a result that looks perfectly reasonable and is quietly wrong.
"""

from fusion import AdaptiveFusion, FixedWeightFusion, make_strategy

FULL = {"face": 1.0, "pose": 1.0, "hands": 1.0}


def test_weights_always_total_one():
    result = AdaptiveFusion().fuse(
        {"face": 70.0, "pose": 60.0, "hands": 50.0},
        {"face": 0.9, "pose": 0.8, "hands": 0.4},
    )
    assert abs(sum(result.weights.values()) - 1.0) < 1e-9


def test_a_channel_below_the_floor_carries_no_influence():
    result = AdaptiveFusion(v_floor=0.2).fuse(
        {"face": 80.0, "pose": 60.0, "hands": 40.0},
        {"face": 1.0, "pose": 1.0, "hands": 0.05},
    )
    assert result.weights["hands"] == 0.0
    # ...and the remaining two share everything equally, so the answer is their mean
    assert abs(result.score - 70.0) < 1e-9


def test_the_first_window_uses_exactly_what_was_measured():
    """The running average has nothing to average against yet, so it starts from the
    reading itself. Starting from the floor value instead would understate every channel
    for the opening seconds of every video."""
    fusion = AdaptiveFusion(alpha=0.6, v_floor=0.2)
    result = fusion.fuse({"face": 50.0, "pose": 50.0, "hands": 50.0}, {"face": 0.9, "pose": 0.8, "hands": 0.7})
    assert result.smoothed_visibility == {"face": 0.9, "pose": 0.8, "hands": 0.7}


def test_smoothing_blends_the_new_reading_into_the_running_average():
    fusion = AdaptiveFusion(alpha=0.6, v_floor=0.0)
    scores = {"face": 50.0, "pose": 50.0, "hands": 50.0}
    fusion.fuse(scores, {"face": 1.0, "pose": 1.0, "hands": 1.0})
    second = fusion.fuse(scores, {"face": 0.0, "pose": 1.0, "hands": 1.0})
    # 0.6 of the new reading plus 0.4 of what came before
    assert abs(second.smoothed_visibility["face"] - 0.4) < 1e-9
    assert abs(second.smoothed_visibility["pose"] - 1.0) < 1e-9


def test_smoothing_stops_one_bad_window_from_evicting_a_channel():
    """A channel that is clearly visible and then vanishes for a single window should not
    be thrown straight out. That is the whole reason the smoothing happens before the
    floor is applied rather than after."""
    fusion = AdaptiveFusion(alpha=0.6, v_floor=0.2)
    scores = {"face": 50.0, "pose": 50.0, "hands": 50.0}
    fusion.fuse(scores, {"face": 1.0, "pose": 1.0, "hands": 1.0})
    dropout = fusion.fuse(scores, {"face": 1.0, "pose": 1.0, "hands": 0.0})
    # smoothed to 0.4, which is still above the floor, so it survives the blip
    assert dropout.weights["hands"] > 0.0
    # but a sustained absence does remove it
    fusion.fuse(scores, {"face": 1.0, "pose": 1.0, "hands": 0.0})
    gone = fusion.fuse(scores, {"face": 1.0, "pose": 1.0, "hands": 0.0})
    assert gone.weights["hands"] == 0.0


def test_nothing_visible_enough_produces_no_score_at_all():
    """When every channel is below the floor there is no defensible number to report, so
    none is reported. A fabricated score would be worse than an admitted gap."""
    result = AdaptiveFusion(v_floor=0.2).fuse(
        {"face": 80.0, "pose": 60.0, "hands": 40.0},
        {"face": 0.05, "pose": 0.05, "hands": 0.05},
    )
    assert result.score is None
    assert all(w is None for w in result.weights.values())


def test_an_unmeasurable_channel_takes_no_part():
    """A channel with no score is a different thing from a channel that scored badly."""
    result = AdaptiveFusion().fuse(
        {"face": 80.0, "pose": 60.0, "hands": None},
        {"face": 1.0, "pose": 1.0, "hands": 0.9},
    )
    assert result.weights["hands"] == 0.0
    assert abs(result.score - 70.0) < 1e-9


def test_a_channel_that_stops_scoring_is_dropped_from_the_share_out():
    """Regression test for a quiet and expensive bug.

    The running average keeps a channel alive for a window or two after it stops being
    measurable. If that lingering value is still allowed a share of the weighting, the
    share is handed to a channel with no score to contribute, and the weights of the
    channels that *did* score no longer total one. The result is a fused score that is
    silently too low, in the window immediately after a dropout, which is exactly the
    moment this whole method exists to handle well.
    """
    fusion = AdaptiveFusion(alpha=0.6, v_floor=0.2)
    scores = {"face": 80.0, "pose": 60.0, "hands": 40.0}
    fusion.fuse(scores, {"face": 1.0, "pose": 1.0, "hands": 1.0})

    dropped = fusion.fuse(
        {"face": 80.0, "pose": 60.0, "hands": None},
        {"face": 1.0, "pose": 1.0, "hands": 0.0},
    )
    assert dropped.weights["hands"] == 0.0
    scoring = dropped.weights["face"] + dropped.weights["pose"]
    assert abs(scoring - 1.0) < 1e-9
    assert abs(dropped.score - 70.0) < 1e-9


def test_the_worked_example_from_the_design_comes_out_right():
    """The design document works through one window by hand. This is that window.

    It publishes the answer as 63.0, which is the rounded figure. Carrying the full
    precision through gives 62.94, and that is what the code should produce. The tiny
    difference is rounding in the write-up, not an error in either place.
    """
    result = AdaptiveFusion(alpha=0.6, v_floor=0.2).fuse(
        {"face": 70.0, "pose": 55.0, "hands": 62.0},
        {"face": 0.90, "pose": 0.80, "hands": 0.08},
    )
    assert result.weights["hands"] == 0.0
    assert abs(result.weights["face"] - 0.90 / 1.70) < 1e-9
    assert abs(result.weights["pose"] - 0.80 / 1.70) < 1e-9
    assert abs(result.score - 62.94) < 0.005


def test_reset_clears_the_running_average_between_videos():
    fusion = AdaptiveFusion(alpha=0.6, v_floor=0.0)
    scores = {"face": 50.0, "pose": 50.0, "hands": 50.0}
    fusion.fuse(scores, {"face": 1.0, "pose": 1.0, "hands": 1.0})
    fusion.reset()
    fresh = fusion.fuse(scores, {"face": 0.3, "pose": 0.3, "hands": 0.3})
    assert fresh.smoothed_visibility["face"] == 0.3  # no memory of the previous video


# --------------------------------------------------------------- the fixed baseline


def test_fixed_weighting_is_equal_by_default():
    result = FixedWeightFusion().fuse({"face": 90.0, "pose": 60.0, "hands": 30.0}, FULL)
    assert all(abs(w - 1.0 / 3.0) < 1e-9 for w in result.weights.values())
    assert abs(result.score - 60.0) < 1e-9


def test_fixed_weighting_ignores_visibility_entirely():
    """This is the point of the baseline, not an oversight. A barely-seen channel keeps
    its full say, which is exactly the behaviour the adaptive method is being tested
    against."""
    scores = {"face": 90.0, "pose": 60.0, "hands": 30.0}
    seen = FixedWeightFusion().fuse(scores, FULL)
    barely = FixedWeightFusion().fuse(scores, {"face": 1.0, "pose": 1.0, "hands": 0.01})
    assert seen.weights == barely.weights
    assert seen.score == barely.score


def test_fixed_weighting_shares_out_a_missing_channel():
    """Being naive about reliability is deliberate. Being arithmetically broken is not.

    A channel with no score has no number to average, so the equal shares are spread over
    the ones that do. Otherwise an absent channel would drag the baseline toward zero and
    make it trivially easy to beat, which would prove nothing.
    """
    result = FixedWeightFusion().fuse({"face": 80.0, "pose": 60.0, "hands": None}, FULL)
    assert result.weights["hands"] == 0.0
    assert abs(result.weights["face"] - 0.5) < 1e-9
    assert abs(result.score - 70.0) < 1e-9


def test_fixed_weighting_accepts_another_split():
    result = FixedWeightFusion({"face": 0.40, "pose": 0.35, "hands": 0.25}).fuse(
        {"face": 100.0, "pose": 0.0, "hands": 0.0}, FULL
    )
    assert abs(result.weights["face"] - 0.40) < 1e-9
    assert abs(result.score - 40.0) < 1e-9


def test_both_agree_when_every_channel_is_equally_visible():
    """With nothing to tell the channels apart, the two methods must give the same answer.
    If they ever disagree here, the difference is coming from somewhere other than
    visibility and the comparison would be measuring the wrong thing."""
    scores = {"face": 80.0, "pose": 60.0, "hands": 40.0}
    adaptive = AdaptiveFusion().fuse(scores, FULL)
    fixed = FixedWeightFusion().fuse(scores, FULL)
    assert abs(adaptive.score - fixed.score) < 1e-9


def test_factory_returns_the_right_strategy():
    assert isinstance(make_strategy("adaptive"), AdaptiveFusion)
    assert isinstance(make_strategy("fixed"), FixedWeightFusion)
