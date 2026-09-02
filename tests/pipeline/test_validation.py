"""Tests for the check that runs when somebody picks a video to analyse.

None of these open a video. The part being tested is the judgement, which is deliberately
separated from the file reading precisely so it can be checked against made-up observations
on any machine, with or without the video library and the detector installed.

What is not covered here is whether the file reading itself reports the right things. That
needs a real video and is checked by running the command against the calibration clips.
"""

import pytest

from validation import (
    DEFAULT_MIN_DURATION_S,
    LOW_RESOLUTION_SHORT_SIDE_PX,
    MAX_DURATION_S,
    MAX_FILE_BYTES,
    MIN_DURATION_CEILING_S,
    MIN_DURATION_FLOOR_S,
    VideoFacts,
    as_json,
    clamp_minimum,
    judge,
)


def facts(**overrides) -> VideoFacts:
    """A file that should be accepted, unless a test changes something about it."""
    base = dict(
        exists=True,
        opened=True,
        file_bytes=200 * 1024 * 1024,
        duration_s=120.0,
        width=1280,
        height=720,
        source_fps=30.0,
        total_frames=3600,
        person_check_ran=True,
        frames_checked=8,
        frames_with_person=8,
    )
    base.update(overrides)
    return VideoFacts(**base)


# --------------------------------------------------------------------- the three refusals


def test_a_missing_file_is_refused():
    result = judge(facts(exists=False))
    assert not result.ok
    assert result.code == "not_found"


def test_a_file_that_will_not_open_is_refused():
    result = judge(facts(opened=False))
    assert not result.ok
    assert result.code == "unreadable"


def test_a_clip_shorter_than_the_minimum_is_refused():
    result = judge(facts(duration_s=25.0), min_duration_s=60.0)
    assert not result.ok
    assert result.code == "too_short"


def test_the_refusal_says_both_lengths_so_the_user_knows_by_how_much():
    """A message saying only "too short" leaves somebody guessing what to record next."""
    result = judge(facts(duration_s=25.0), min_duration_s=60.0)
    assert "25" in result.reason and "60" in result.reason


def test_a_clip_longer_than_the_hard_cap_is_refused():
    """The upper limit exists for a different reason from the lower one: not "too little to
    analyse" but "too long to sit through", since analysis runs at roughly video speed."""
    result = judge(facts(duration_s=MAX_DURATION_S + 1))
    assert not result.ok
    assert result.code == "too_long"


def test_a_file_larger_than_the_size_limit_is_refused():
    """Refused before the file is even opened, because the video gets copied into the
    session folder and a careless upload should not be able to fill the disk."""
    result = judge(facts(file_bytes=MAX_FILE_BYTES + 1))
    assert not result.ok
    assert result.code == "too_large"


def test_the_size_limit_is_checked_before_the_file_is_opened():
    """An oversized file is refused on its size alone, even though nothing managed to open
    it. Reporting it as unreadable would send the user off to fix the wrong problem."""
    result = judge(facts(file_bytes=MAX_FILE_BYTES + 1, opened=False))
    assert result.code == "too_large"


def test_an_empty_room_is_refused():
    result = judge(facts(frames_with_person=0))
    assert not result.ok
    assert result.code == "no_person"


# ------------------------------------------------------------- what should still be allowed


def test_a_good_file_is_accepted():
    result = judge(facts())
    assert result.ok
    assert result.code == "ok"
    assert result.reason == ""


def test_a_clip_exactly_at_the_minimum_is_accepted():
    """The minimum is a floor, not something to be above, and off-by-one here would be an
    unpleasant surprise for anyone recording a clip to the length they were told."""
    assert judge(facts(duration_s=60.0), min_duration_s=60.0).ok


def test_someone_visible_in_half_the_frames_is_accepted_with_a_warning():
    """Somebody who steps out of shot for part of a clip still gets their analysis. The
    weighting is built to handle exactly that, so refusing it would be refusing the case the
    project exists to deal with."""
    result = judge(facts(frames_checked=8, frames_with_person=4))
    assert result.ok
    assert any("every frame" in w for w in result.warnings)


def test_a_low_resolution_video_is_warned_about_rather_than_refused():
    """Pixel count is a poor way to decide this when the check is about to look at the actual
    footage. If somebody is plainly visible in a small frame, refusing it would be arguing
    with the evidence the check has just gathered."""
    result = judge(facts(width=320, height=240))
    assert result.ok
    assert any("low resolution" in w for w in result.warnings)


def test_a_normal_resolution_video_gets_no_such_warning():
    result = judge(facts(width=1280, height=720))
    assert not any("low resolution" in w for w in result.warnings)


def test_a_portrait_video_is_judged_on_its_shorter_side():
    """Phone footage is usually taller than it is wide, and its width is the side that
    limits how much detail there is to measure."""
    tall_but_narrow = judge(facts(width=360, height=1280))
    assert any("low resolution" in w for w in tall_but_narrow.warnings)
    tall_and_fine = judge(facts(width=720, height=1280))
    assert not any("low resolution" in w for w in tall_and_fine.warnings)
    assert LOW_RESOLUTION_SHORT_SIDE_PX == 480


def test_an_unreadable_length_is_a_warning_and_not_a_refusal():
    """Some files never report how long they are. That is the file's bookkeeping, not the
    user's fault, and the analysis works regardless."""
    result = judge(facts(duration_s=0.0))
    assert result.ok
    assert any("length" in w for w in result.warnings)


def test_the_single_person_limit_is_always_mentioned():
    """It cannot be enforced, because the detector only ever returns one person, so saying
    it plainly every time is the only honest way to handle it."""
    result = judge(facts())
    assert any("one person" in w for w in result.warnings)


# ------------------------------------------------- the detector being missing is not a verdict


def test_a_missing_detector_does_not_become_an_empty_room():
    """The distinction the whole check turns on. "Nobody is in this video" is a fact about
    the video; "the detector is not installed" is a fact about the computer. Confusing the
    two would refuse a perfectly good recording on the strength of a missing library."""
    result = judge(facts(person_check_ran=False, frames_checked=0, frames_with_person=0))
    assert result.ok
    assert any("could not be checked" in w for w in result.warnings)


def test_no_frames_sampled_is_not_an_empty_room_either():
    result = judge(facts(person_check_ran=True, frames_checked=0, frames_with_person=0))
    assert result.ok


# ------------------------------------------------------------------ the configurable minimum


@pytest.mark.parametrize(
    "given, expected",
    [
        (0.0, DEFAULT_MIN_DURATION_S),  # unset falls back to the default
        (-5.0, DEFAULT_MIN_DURATION_S),
        (10.0, MIN_DURATION_FLOOR_S),  # below the allowed range
        (600.0, MIN_DURATION_CEILING_S),  # above it
        (90.0, 90.0),  # inside it, left alone
    ],
)
def test_the_minimum_length_setting_is_kept_inside_the_allowed_range(given, expected):
    assert clamp_minimum(given) == expected


def test_an_absurd_setting_cannot_reject_a_reasonable_clip():
    """Follows from the clamping above, but it is the consequence that actually matters:
    a bad setting must not be able to turn away a perfectly normal practice video."""
    assert judge(facts(duration_s=200.0), min_duration_s=100000.0).ok


# ------------------------------------------------------------------- the message to the app


def test_the_reported_shape_matches_what_the_application_reads():
    payload = as_json(judge(facts(duration_s=93.46)))
    assert set(payload) == {
        "ok",
        "code",
        "reason",
        "durationS",
        "width",
        "height",
        "sourceFps",
        "warnings",
    }
    assert payload["durationS"] == 93.5
    assert isinstance(payload["warnings"], list)


def test_a_refusal_still_reports_what_was_measured():
    """The length is wanted even when the file was turned away, because it is what the
    message is explaining and it is worth recording against the session."""
    payload = as_json(judge(facts(duration_s=25.0), min_duration_s=60.0))
    assert payload["ok"] is False
    assert payload["durationS"] == 25.0


def test_a_missing_video_library_is_reported_rather_than_blamed_on_the_video(monkeypatch):
    """The same distinction as the detector one above, one level further down.

    If the library that opens videos is not installed, nothing here can look at the file at
    all. Returning "this video is unreadable" would blame the user's recording for a missing
    piece of this program, and would do it in a message telling them to go and re-record
    something that was never the problem. It has to surface as a check that did not happen.
    """
    import sys

    import validation

    monkeypatch.setitem(sys.modules, "cv2", None)
    with pytest.raises(RuntimeError, match="not installed"):
        validation._read_facts(__file__)
