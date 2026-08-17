"""Tests for the two ways of combining channel scores.

These matter more than most tests in the project. The comparison between adaptive and fixed
weighting is the thing being investigated, so a mistake in either one would not show up as a
crash. It would show up as a result that looks perfectly reasonable and is quietly wrong.
"""

from fusion import AdaptiveFusion, FixedWeightFusion, make_strategy


def test_adaptive_weights_sum_to_one():
    w = AdaptiveFusion().weights({"face": 0.9, "pose": 0.8, "hands": 0.0})
    assert abs(sum(w.values()) - 1.0) < 1e-9
    # An invisible channel carries zero influence.
    assert w["hands"] == 0.0


def test_adaptive_all_zero_visibility():
    w = AdaptiveFusion().weights({"face": 0.0, "pose": 0.0, "hands": 0.0})
    assert all(v == 0.0 for v in w.values())


def test_fixed_is_equal_weighting_by_default():
    w = FixedWeightFusion().weights({"face": 0.1, "pose": 0.9, "hands": 0.5})
    assert all(abs(v - 1.0 / 3.0) < 1e-9 for v in w.values())


def test_adaptive_fuse_excludes_invisible_channel():
    fused = AdaptiveFusion().fuse(
        {"face": 80.0, "pose": 60.0, "hands": 40.0},
        {"face": 1.0, "pose": 1.0, "hands": 0.0},
    )
    # hands dropped → mean of face & pose = 70.
    assert abs(fused - 70.0) < 1e-9


def test_factory_returns_the_right_strategy():
    assert isinstance(make_strategy("adaptive"), AdaptiveFusion)
    assert isinstance(make_strategy("fixed"), FixedWeightFusion)
