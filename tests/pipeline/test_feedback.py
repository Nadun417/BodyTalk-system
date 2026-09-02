"""Tests for the rules that decide what gets said, and when.

The behaviour worth pinning down here is mostly about restraint. Almost every rule is a
statement about how long something has to go on before it is worth mentioning, so most of
these tests are checking that brief, ordinary movements stay quiet.
"""

from dataclasses import dataclass

from feedback import (
    Event,
    all_events,
    clock,
    face_events,
    hand_events,
    pose_events,
    recommendations,
    summarise,
    sustained_intervals,
)


# Stand-ins for the analyser outputs, carrying only the fields the rules read.
@dataclass
class FaceW:
    t_start_s: float
    t_end_s: float
    facing: float | None = 100.0
    liveliness: float | None = 100.0
    stability: float | None = 100.0
    mouth_width: float | None = 0.50
    score: float | None = 100.0


@dataclass
class PoseW:
    t_start_s: float
    t_end_s: float
    uprightness: float | None = 100.0
    levelness: float | None = 100.0
    sway: float | None = 100.0
    score: float | None = 100.0


@dataclass
class HandW:
    t_start_s: float
    t_end_s: float
    visibility: float = 1.0
    gesture_raw: float | None = 0.35
    fidget: float | None = 100.0
    touch_raw: float | None = 0.0
    score: float | None = 100.0


def seconds(n, factory, **overrides):
    """n one-second windows, all identical."""
    return [factory(t_start_s=float(t), t_end_s=float(t + 1), **overrides) for t in range(n)]


# ------------------------------------------------------------------- the interval helper


def test_a_brief_condition_is_not_reported():
    flags = [(0.0, 1.0, True), (1.0, 2.0, True), (2.0, 3.0, False)]
    assert sustained_intervals(flags, min_duration_s=5.0) == []


def test_a_sustained_condition_is_reported():
    flags = [(float(t), float(t + 1), True) for t in range(6)]
    assert sustained_intervals(flags, min_duration_s=5.0) == [(0.0, 6.0)]


def test_one_recovered_second_does_not_split_an_interval():
    """Somebody who slouches for twenty seconds and sits up for one has slouched once,
    not twice, and should be told so once."""
    flags = [(float(t), float(t + 1), t != 10) for t in range(20)]
    assert sustained_intervals(flags, min_duration_s=5.0) == [(0.0, 20.0)]


def test_a_long_gap_does_split_an_interval():
    flags = [(float(t), float(t + 1), t < 6 or t >= 14) for t in range(20)]
    result = sustained_intervals(flags, min_duration_s=3.0, merge_within_s=0.0)
    assert len(result) == 2


def test_nearby_intervals_are_merged_into_one_observation():
    """A two-second gap is short enough that this is one observation, not two.

    The gap is too long for the one-second tolerance, so the run does close, but the two
    halves are then merged. Telling somebody they leaned at 0:00 and again at 0:08 is
    really telling them the same thing twice.
    """
    flags = [(float(t), float(t + 1), t < 6 or t >= 8) for t in range(16)]
    assert sustained_intervals(flags, min_duration_s=3.0) == [(0.0, 16.0)]


def test_a_gap_wider_than_the_merge_window_stays_two_observations():
    flags = [(float(t), float(t + 1), t < 6 or t >= 9) for t in range(16)]
    assert sustained_intervals(flags, min_duration_s=3.0) == [(0.0, 6.0), (9.0, 16.0)]


def test_clock_formats_as_a_video_position():
    assert clock(0) == "0:00"
    assert clock(9) == "0:09"
    assert clock(83) == "1:23"


# --------------------------------------------------------------------------- face rules


def test_a_glance_away_is_not_flagged_but_a_sustained_look_away_is():
    brief = seconds(3, FaceW, facing=10.0)
    assert [e for e in face_events(brief) if e.type == "looking_away"] == []

    sustained = seconds(8, FaceW, facing=10.0)
    found = [e for e in face_events(sustained) if e.type == "looking_away"]
    assert len(found) == 1
    assert found[0].severity == "medium"
    assert "0:00" in found[0].message


def test_a_flat_expression_needs_a_long_stretch_before_it_is_mentioned():
    assert [e for e in face_events(seconds(15, FaceW, liveliness=5.0)) if e.type == "flat_expression"] == []
    assert [e for e in face_events(seconds(25, FaceW, liveliness=5.0)) if e.type == "flat_expression"]


def test_windows_that_could_not_be_measured_are_not_treated_as_faults():
    """Not measurable is not the same as bad, and must never be counted as bad."""
    assert face_events(seconds(30, FaceW, facing=None, liveliness=None, stability=None)) == []


def test_a_smile_is_found_against_the_persons_own_resting_mouth_width():
    windows = seconds(20, FaceW)
    for w in windows[5:9]:
        w.mouth_width = 0.50 * 1.3  # noticeably wider than this person's median
    found = [e for e in face_events(windows) if e.type == "smile"]
    assert len(found) == 1
    assert found[0].severity == "info"


def test_smiling_is_never_reported_as_a_fault():
    windows = seconds(20, FaceW)
    for w in windows[5:12]:
        w.mouth_width = 0.50 * 1.3
    assert all(e.severity == "info" for e in face_events(windows) if e.type == "smile")


# --------------------------------------------------------------------------- pose rules


def test_leaning_off_upright_is_reported_after_three_seconds():
    assert [e for e in pose_events(seconds(2, PoseW, uprightness=10.0)) if e.type == "slouching"] == []
    assert [e for e in pose_events(seconds(6, PoseW, uprightness=10.0)) if e.type == "slouching"]


def test_the_upright_message_does_not_claim_to_detect_a_forward_slouch():
    """The measurement is taken in the flat image and cannot see movement toward the
    camera, so the wording must not imply otherwise."""
    found = [e for e in pose_events(seconds(6, PoseW, uprightness=10.0)) if e.type == "slouching"]
    assert "forward" not in found[0].message.lower()


def test_leaning_to_one_side_needs_ten_seconds():
    assert [e for e in pose_events(seconds(6, PoseW, levelness=10.0)) if e.type == "leaning_to_side"] == []
    assert [e for e in pose_events(seconds(14, PoseW, levelness=10.0)) if e.type == "leaning_to_side"]


# --------------------------------------------------------------------------- hand rules


def test_hands_out_of_frame_is_measured_on_visibility_not_on_a_score():
    """When the hands are out of shot there is no score to test, so this rule reads the
    visibility instead. It is the one observation about framing rather than behaviour."""
    windows = seconds(15, HandW, visibility=0.0, gesture_raw=None, fidget=None, touch_raw=None, score=None)
    found = [e for e in hand_events(windows) if e.type == "hands_out_of_frame"]
    assert len(found) == 1
    assert found[0].severity == "info"


def test_still_hands_need_a_full_thirty_seconds():
    assert [e for e in hand_events(seconds(20, HandW, gesture_raw=0.01)) if e.type == "low_gesture"] == []
    assert [e for e in hand_events(seconds(35, HandW, gesture_raw=0.01)) if e.type == "low_gesture"]


def test_busy_hands_are_flagged_sooner_than_still_ones():
    assert [e for e in hand_events(seconds(12, HandW, gesture_raw=0.9)) if e.type == "excessive_gesture"]


def test_fidgeting_requires_eight_seconds_not_five():
    """Raised deliberately. The measurement separates fidgeting from ordinary talking by
    only about a third, so it needs more evidence before it says anything."""
    assert [e for e in hand_events(seconds(6, HandW, fidget=10.0)) if e.type == "fidgeting"] == []
    assert [e for e in hand_events(seconds(10, HandW, fidget=10.0)) if e.type == "fidgeting"]


def test_a_hand_at_the_face_is_reported_quickly():
    assert [e for e in hand_events(seconds(3, HandW, touch_raw=0.9)) if e.type == "hand_to_face"]


# ------------------------------------------------------------ ordering and what to try


def test_events_come_back_in_time_order():
    face = seconds(40, FaceW)
    for w in face[30:38]:
        w.facing = 10.0
    pose = seconds(40, PoseW)
    for w in pose[2:10]:
        w.uprightness = 10.0
    events = all_events(face, pose, seconds(40, HandW))
    assert [e.t_start_s for e in events] == sorted(e.t_start_s for e in events)


def _fault(channel, severity, seconds_long=10.0):
    return Event(0.0, seconds_long, channel, "x", severity, "Something happened.", "Try this.")


def test_the_channel_with_the_most_sustained_trouble_is_ranked_first():
    events = [_fault("pose", "medium", 30.0), _fault("hands", "low", 5.0)]
    result = recommendations(events, {"face": 90.0, "pose": 50.0, "hands": 80.0})
    assert result[0].channel == "pose"
    assert result[0].kind == "improve"


def test_the_advice_always_finishes_with_something_that_went_well():
    events = [_fault("pose", "medium", 30.0)]
    result = recommendations(events, {"face": 92.0, "pose": 50.0, "hands": 80.0})
    assert result[-1].kind == "maintain"
    assert result[-1].channel == "face"  # the highest scoring channel


def test_no_more_than_three_suggestions_are_given():
    events = [_fault("pose", "medium", 30.0), _fault("hands", "medium", 25.0), _fault("face", "medium", 20.0)]
    assert len(recommendations(events, {"face": 40.0, "pose": 30.0, "hands": 35.0})) <= 3


def test_positive_moments_never_push_a_channel_up_the_list():
    """A smile is not something to fix, so it must carry no weight in the ranking."""
    smiles = [Event(0.0, 30.0, "face", "smile", "info", "Nice smile.", "Keep it.")]
    result = recommendations(smiles, {"face": 50.0, "pose": 90.0, "hands": 90.0})
    assert all(r.kind != "improve" or r.channel != "face" for r in result)


def test_the_same_analysis_always_produces_the_same_advice():
    """The comparison between fusion modes would be meaningless if this varied."""
    events = [_fault("pose", "medium", 20.0), _fault("hands", "medium", 20.0)]
    scores = {"face": 70.0, "pose": 70.0, "hands": 70.0}
    first = recommendations(events, scores)
    for _ in range(5):
        repeat = recommendations(events, scores)
        assert [(r.rank, r.channel, r.kind) for r in repeat] == [
            (r.rank, r.channel, r.kind) for r in first
        ]


# ------------------------------------------------------------------------- the summary


def test_unscored_windows_are_left_out_rather_than_counted_as_zero():
    """Counting them as zero would punish somebody for their camera framing."""
    summary = summarise(
        fused_scores=[80.0, None, None, 90.0],
        channel_windows={"face": seconds(4, FaceW, score=85.0)},
        events=[],
        duration_s=4.0,
    )
    assert summary.overall_score == 85.0  # the mean of 80 and 90, not of 80, 0, 0, 90
    assert summary.facts.windows_skipped == 2


def test_a_session_with_nothing_visible_says_so_rather_than_scoring_zero():
    summary = summarise([None, None], {"face": []}, [], 2.0)
    assert summary.overall_score is None
    assert "not enough" in summary.summary_text.lower()


def test_the_summary_names_a_strength_and_something_to_work_on():
    events = [Event(10.0, 40.0, "pose", "slouching", "medium", "You leaned.", "Sit tall.")]
    summary = summarise(
        [80.0] * 60,
        {"face": seconds(60, FaceW, score=90.0), "pose": seconds(60, PoseW, score=50.0)},
        events,
        60.0,
    )
    assert summary.facts.strongest_channel == "face"
    assert summary.facts.weakest_channel == "pose"
    assert "strongest" in summary.summary_text
    assert "work on" in summary.summary_text


def test_a_thinly_evidenced_session_is_flagged_as_such():
    summary = summarise([80.0] + [None] * 9, {"face": []}, [], 10.0)
    assert "less evidence" in summary.summary_text


def test_a_channel_is_never_both_the_thing_to_fix_and_the_thing_to_keep():
    """Caught on real footage. A channel can score well overall and still hold the most
    sustained trouble, which produced "work on your posture" directly above "keep doing
    what you did with your posture" in the same list."""
    events = [
        Event(0.0, 40.0, "pose", "slouching", "medium", "You leaned.", "Sit tall."),
        Event(0.0, 5.0, "face", "looking_away", "medium", "You looked away.", "Look up."),
    ]
    result = recommendations(events, {"face": 60.0, "pose": 87.0, "hands": 76.0})
    improve = {r.channel for r in result if r.kind == "improve"}
    maintain = {r.channel for r in result if r.kind == "maintain"}
    assert not (improve & maintain)
