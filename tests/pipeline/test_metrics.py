"""Tests for breaking a channel score back apart into the measurements that produced it.

The property that matters most here is that the split is exact. Each measurement is
credited with a number of points, and those points have to add back up to the channel's
actual shortfall with nothing left over, or the numbers shown to the user are made up. Most
of these tests exist to hold that line under the awkward cases: a measurement missing from
some windows, a channel that could not be scored at all, a measurement that is recorded but
deliberately does not count toward the score.
"""

from __future__ import annotations

import statistics as stats
from dataclasses import dataclass

import pytest

from analysers import CHANNEL_METRICS
from feedback.metrics import (
    NEGLIGIBLE_SHORTFALL,
    driving_metric,
    explain_channel,
    metric_reports,
)


@dataclass
class FakeFace:
    """Stands in for a real face window. Only the fields the breakdown reads."""

    score: float | None
    facing: float | None
    liveliness: float | None
    stability: float | None


@dataclass
class FakeHands:
    score: float | None
    gesture: float | None
    touch: float | None
    fidget: float | None


def face(facing, liveliness, stability):
    """Build a face window whose score is the mean of whichever parts are present.

    Worked out here the same way the real analyser works it out, so that these tests are
    checking the breakdown rather than quietly agreeing with it about a wrong number.
    """
    parts = [p for p in (facing, liveliness, stability) if p is not None]
    return FakeFace(
        score=stats.fmean(parts) if parts else None,
        facing=facing,
        liveliness=liveliness,
        stability=stability,
    )


def hands(gesture, touch, fidget):
    """Same, but for hands, where fidgeting is measured and deliberately not scored."""
    parts = [p for p in (gesture, touch) if p is not None]
    return FakeHands(
        score=stats.fmean(parts) if parts else None,
        gesture=gesture,
        touch=touch,
        fidget=fidget,
    )


def channel_mean(windows):
    scored = [w.score for w in windows if w.score is not None]
    return stats.fmean(scored) if scored else None


# --------------------------------------------------------------- the exactness property


def test_the_shortfalls_add_up_to_the_channel_shortfall():
    windows = [face(100, 0, 100), face(100, 0, 100), face(100, 0, 100)]
    reports = metric_reports({"face": windows})["face"]

    assert channel_mean(windows) == pytest.approx(200 / 3)
    assert sum(r.shortfall for r in reports) == pytest.approx(100 - 200 / 3)


def test_it_stays_exact_when_a_measurement_is_missing_from_some_windows():
    """The hard case: the divisor changes window by window.

    A window with two measurements splits its shortfall two ways; a window with three
    splits it three ways. Charging a measurement for a window it was absent from, or
    dividing by a fixed number of measurements, both break here.
    """
    windows = [
        face(100, 0, 100),  # three measurements
        face(60, None, 40),  # two, so each carries half of this window
        face(None, 20, None),  # one, carrying all of it
    ]
    reports = metric_reports({"face": windows})["face"]
    assert sum(r.shortfall for r in reports) == pytest.approx(100 - channel_mean(windows))


def test_it_stays_exact_when_some_windows_have_no_score_at_all():
    """Unscored windows are missing evidence and the channel score already ignores them."""
    windows = [face(100, 0, 100), face(None, None, None), face(80, 40, 90)]
    reports = metric_reports({"face": windows})["face"]
    assert sum(r.shortfall for r in reports) == pytest.approx(100 - channel_mean(windows))


def test_a_perfect_channel_has_no_shortfall_anywhere():
    reports = metric_reports({"face": [face(100, 100, 100)] * 5})["face"]
    assert all(r.shortfall == pytest.approx(0.0) for r in reports)
    assert driving_metric(reports) is None


# ------------------------------------------------- the measurement that does not count


def test_fidgeting_is_reported_but_never_blamed():
    """It is measured, it is kept as evidence, and it had no part in the score.

    This is the test that stops the breakdown telling somebody their hand score was
    dragged down by fidgeting. It was not: fidgeting was withdrawn from the score after
    it proved unreliable, so naming it would be pointing at the one number that had no
    influence on the result.
    """
    windows = [hands(gesture=90, touch=90, fidget=0)] * 4
    reports = metric_reports({"hands": windows})["hands"]

    fidget = next(r for r in reports if r.metric == "fidget")
    assert fidget.scored is False
    assert fidget.shortfall == 0.0
    assert fidget.mean_score == 0.0  # still reported, so it stays available as evidence
    assert driving_metric(reports) is None or driving_metric(reports).metric != "fidget"


def test_the_unscored_measurement_never_wins_the_explanation():
    """Even when it is by far the worst number in the channel."""
    windows = [hands(gesture=70, touch=100, fidget=0)] * 4
    reports = metric_reports({"hands": windows})["hands"]
    assert driving_metric(reports).metric == "gesture"
    assert "fidget" not in (explain_channel(85.0, reports) or "")


# ------------------------------------------------------------------ ordering and choice


def test_reports_come_back_worst_first():
    windows = [face(facing=100, liveliness=10, stability=60)] * 3
    reports = metric_reports({"face": windows})["face"]
    assert [r.metric for r in reports] == ["liveliness", "stability", "facing"]


def test_the_driver_is_the_biggest_contributor_not_the_lowest_average():
    """These come apart when coverage differs, and the shortfall is the honest one.

    A measurement that reads badly in two windows out of twenty did less to the score than
    one reading moderately in all twenty, even though its average is lower.
    """
    windows = [face(facing=100, liveliness=None, stability=50) for _ in range(18)]
    windows += [face(facing=100, liveliness=0, stability=50) for _ in range(2)]
    reports = metric_reports({"face": windows})["face"]

    liveliness = next(r for r in reports if r.metric == "liveliness")
    stability = next(r for r in reports if r.metric == "stability")
    assert liveliness.mean_score < stability.mean_score
    assert stability.shortfall > liveliness.shortfall
    assert driving_metric(reports).metric == "stability"


def test_nothing_is_named_when_no_measurement_meaningfully_held_the_channel_back():
    """A good score should not have a culprit invented for it."""
    windows = [face(99, 99, 99)] * 5
    reports = metric_reports({"face": windows})["face"]
    assert all(r.shortfall < NEGLIGIBLE_SHORTFALL for r in reports)
    assert explain_channel(99.0, reports) is None


# ----------------------------------------------------------------------- coverage


def test_coverage_reports_how_much_of_the_session_a_measurement_covered():
    windows = [face(100, 50, 100)] * 5 + [face(100, None, 100)] * 5
    reports = metric_reports({"face": windows})["face"]
    liveliness = next(r for r in reports if r.metric == "liveliness")
    assert liveliness.windows == 5
    assert liveliness.coverage == pytest.approx(0.5)


def test_thin_coverage_is_admitted_in_the_sentence():
    """A finding from a fifth of the video should not be stated as flatly as one from all of it."""
    windows = [face(100, 0, 100)] * 2 + [face(100, None, 100)] * 8
    reports = metric_reports({"face": windows})["face"]
    sentence = explain_channel(channel_mean(windows), reports)
    assert "hint rather than a finding" in sentence


# ------------------------------------------------------------------- the sentence


def test_the_sentence_names_the_measurement_and_what_went_well():
    windows = [face(facing=100, liveliness=2, stability=97)] * 10
    sentence = explain_channel(channel_mean(windows), metric_reports({"face": windows})["face"])

    assert "expression variation" in sentence
    # The comparison is the point: without it the sentence reads as though the whole
    # channel was weak, which is the misreading this exists to correct.
    assert "head steadiness" in sentence and "facing the camera" in sentence
    assert sentence.endswith(".")


def test_no_sentence_for_a_channel_that_was_never_scored():
    windows = [face(None, None, None)] * 4
    assert explain_channel(None, metric_reports({"face": windows})["face"]) is None


def test_the_sentence_says_nothing_about_how_anybody_felt():
    """The wording is bound by the same rule as everything else the user reads."""
    windows = [face(facing=30, liveliness=5, stability=40)] * 10
    sentence = explain_channel(channel_mean(windows), metric_reports({"face": windows})["face"])
    for word in ("nervous", "anxious", "confident", "confidence", "uncomfortable", "personality"):
        assert word not in sentence.lower()


# ------------------------------------------------------------------ the labels


def test_every_measurement_has_wording_a_stranger_could_read():
    """The labels reach the user, so none of them may be an internal field name."""
    for channel, specs in CHANNEL_METRICS.items():
        for spec in specs:
            assert spec.label and spec.label != spec.attribute
            assert spec.label == spec.label.lower(), f"{spec.label} should not be capitalised"


def test_the_hand_channel_is_the_only_one_with_a_measurement_that_does_not_count():
    unscored = {
        (channel, spec.attribute)
        for channel, specs in CHANNEL_METRICS.items()
        for spec in specs
        if not spec.scored
    }
    assert unscored == {("hands", "fidget")}
