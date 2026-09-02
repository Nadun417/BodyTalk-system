"""Tests for the assembly line and the file it hands to the desktop application.

These run against a small landmark cache written by hand, so they never need a video, a
camera, OpenCV or MediaPipe. That keeps them fast and lets them run anywhere.

The test that matters most here is the last one. The whole project rests on being able to
say that two runs of the same video differed *only* in how the channels were weighted. If
anything else ever varies between the two, the comparison stops meaning anything, and it
would not fail loudly. It would just quietly produce a result that looks reasonable.
"""

import json
import math

from fusion import AdaptiveFusion, FixedWeightFusion
from pipeline import Pipeline
from serialisation.results import read_results


def _face(turn: float = 0.0, mouth: float = 0.10) -> list:
    lm = [[0.0, 0.0, 0.0] for _ in range(468)]
    lm[1] = [0.50 + turn, 0.50, 0.0]  # nose tip
    lm[33] = [0.40, 0.50, 0.0]  # right eye outer
    lm[263] = [0.60, 0.50, 0.0]  # left eye outer
    lm[13] = [0.50, 0.60, 0.0]  # inner upper lip
    lm[14] = [0.50, 0.60 + mouth, 0.0]  # inner lower lip
    lm[105] = [0.40, 0.44, 0.0]
    lm[334] = [0.60, 0.44, 0.0]
    lm[61] = [0.45, 0.62, 0.0]
    lm[291] = [0.55, 0.62, 0.0]
    lm[152] = [0.50, 0.72, 0.0]
    lm[234] = [0.40, 0.50, 0.0]  # cheeks, the face-width reference
    lm[454] = [0.60, 0.50, 0.0]
    return lm


def _pose(visibility: float = 1.0) -> list:
    lm = [[0.0, 0.0, 0.0, 0.0] for _ in range(33)]
    lm[0] = [0.50, 0.40, 0.0, visibility]  # nose
    lm[3] = [0.53, 0.40, 0.0, visibility]  # left eye outer
    lm[6] = [0.47, 0.40, 0.0, visibility]  # right eye outer
    lm[11] = [0.60, 0.60, 0.0, visibility]  # left shoulder
    lm[12] = [0.40, 0.60, 0.0, visibility]  # right shoulder
    lm[13] = [0.62, 0.75, 0.0, visibility]
    lm[14] = [0.38, 0.75, 0.0, visibility]
    return lm


def _hand(x: float) -> list:
    return [[x, 0.80, 0.0] for _ in range(21)]


def write_cache(path, seconds: int = 12, both_until: int = 5, one_until: int = 9) -> None:
    """A small cache in three phases: both hands, then one hand, then none.

    The middle phase is the important one and it is easy to leave out. With hands either
    fully visible or fully gone, the two weighting strategies agree exactly — correctly so,
    because there is nothing for one to be cleverer about. They only diverge when a channel
    is *partly* visible, so a test fixture without a partly-visible stretch cannot
    demonstrate the difference between them at all.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    header = {
        "type": "header",
        "schemaVersion": 1,
        "video": "synthetic.mp4",
        "videoDurationS": float(seconds),
        "sourceFps": 30.0,
        "analysisFps": 6.0,
        "frame": {"width": 1280, "height": 720},
        "mediapipe": {"version": "test", "refineFaceLandmarks": False},
        "createdAt": "2026-09-02T12:00:00+05:30",
    }
    lines = [json.dumps(header)]
    for i in range(seconds * 6):
        t = i / 6.0
        both = t < both_until
        one = both_until <= t < one_until
        wobble = 0.02 * math.sin(i)
        lines.append(
            json.dumps(
                {
                    "type": "frame",
                    "frameIndex": i * 5,
                    "tS": round(t, 3),
                    "face": {"detected": True, "landmarks": _face(mouth=0.10 + wobble)},
                    "pose": {"detected": True, "landmarks": _pose()},
                    "leftHand": {
                        "detected": both or one,
                        "landmarks": _hand(0.30 + wobble) if (both or one) else None,
                    },
                    "rightHand": {
                        "detected": both,
                        "landmarks": _hand(0.70 - wobble) if both else None,
                    },
                }
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_both(tmp_path):
    """Analyse the same cache twice, changing only the weighting strategy."""
    results = {}
    for name, strategy in (("adaptive", AdaptiveFusion()), ("fixed", FixedWeightFusion())):
        out = tmp_path / name
        write_cache(out / "landmarks.jsonl")
        Pipeline(strategy).run("synthetic.mp4", out_dir=str(out))
        results[name] = read_results(out / "results.json")
    return results


def test_the_pipeline_writes_a_results_file(tmp_path):
    out = tmp_path / "session"
    write_cache(out / "landmarks.jsonl")
    result = Pipeline(AdaptiveFusion()).run("synthetic.mp4", out_dir=str(out))
    assert (out / "results.json").exists()
    assert read_results(out / "results.json") == result


def test_the_result_has_every_field_the_application_reads(tmp_path):
    out = tmp_path / "session"
    write_cache(out / "landmarks.jsonl")
    result = Pipeline(AdaptiveFusion()).run("synthetic.mp4", out_dir=str(out))
    for key in (
        "schemaVersion",
        "fusionMode",
        "overallScore",
        "channelScores",
        "overallSummary",
        "summaryPhrasing",
        "windows",
        "events",
        "recommendations",
        "meta",
    ):
        assert key in result, f"missing {key}"
    assert result["schemaVersion"] == 2
    assert result["fusionMode"] == "adaptive"


def test_every_window_produces_four_rows(tmp_path):
    """Three channels and their combined result, which is the shape the database wants."""
    out = tmp_path / "session"
    write_cache(out / "landmarks.jsonl", seconds=10)
    result = Pipeline(AdaptiveFusion()).run("synthetic.mp4", out_dir=str(out))
    rows = result["windows"]
    assert len(rows) % 4 == 0
    assert [r["channel"] for r in rows[:4]] == ["face", "pose", "hands", "fused"]


def test_the_combined_row_carries_no_visibility_or_weight(tmp_path):
    """It is the product of the three above it, not a fourth thing that was measured."""
    out = tmp_path / "session"
    write_cache(out / "landmarks.jsonl")
    result = Pipeline(AdaptiveFusion()).run("synthetic.mp4", out_dir=str(out))
    fused = [r for r in result["windows"] if r["channel"] == "fused"]
    assert fused
    assert all(r["visibility"] is None and r["weight"] is None for r in fused)


def test_only_pinned_event_types_can_appear(tmp_path):
    """The vocabulary is shared with the database and the dashboard, so an unrecognised
    type here would surface as a bug in a layer that has not been written yet."""
    vocabulary = {
        "looking_away",
        "flat_expression",
        "smile",
        "head_movement",
        "slouching",
        "leaning_to_side",
        "restlessness",
        "hands_out_of_frame",
        "low_gesture",
        "excessive_gesture",
        "hand_to_face",
    }
    out = tmp_path / "session"
    write_cache(out / "landmarks.jsonl", seconds=40)
    result = Pipeline(AdaptiveFusion()).run("synthetic.mp4", out_dir=str(out))
    assert {e["type"] for e in result["events"]} <= vocabulary


def test_the_settings_used_are_recorded_with_the_result(tmp_path):
    """A result nobody can reproduce is not evidence."""
    out = tmp_path / "session"
    write_cache(out / "landmarks.jsonl")
    result = Pipeline(AdaptiveFusion(alpha=0.6, v_floor=0.2)).run("synthetic.mp4", out_dir=str(out))
    assert result["meta"]["fusionParams"] == {"alpha": 0.6, "vFloor": 0.2}
    assert result["meta"]["windowS"] == 1.0


def test_the_two_strategies_differ_in_their_weights_and_in_nothing_else(tmp_path):
    """The guarantee the entire comparison rests on.

    Run the same video twice, changing only which weighting object was handed in. The
    per-channel scores must come back identical, because the analysers never see the
    strategy. The observations must be identical, because they are read off those same
    per-channel scores. Only the weights, and therefore the combined score, may move.

    If anything else ever differs, the comparison is measuring something other than the
    weighting, and it would not announce itself. It would simply produce a plausible number
    that means nothing.
    """
    results = run_both(tmp_path)
    adaptive, fixed = results["adaptive"], results["fixed"]

    assert adaptive["channelScores"] == fixed["channelScores"]
    assert [e["type"] for e in adaptive["events"]] == [e["type"] for e in fixed["events"]]
    assert [(e["tStartS"], e["tEndS"]) for e in adaptive["events"]] == [
        (e["tStartS"], e["tEndS"]) for e in fixed["events"]
    ]

    per_channel = lambda r: [
        (w["channel"], w["rawScore"]) for w in r["windows"] if w["channel"] != "fused"
    ]
    assert per_channel(adaptive) == per_channel(fixed)

    weights = lambda r: [w["weight"] for w in r["windows"] if w["channel"] == "hands"]
    assert weights(adaptive) != weights(fixed)


def test_the_hand_channel_loses_influence_when_the_hands_go_missing(tmp_path):
    """The behaviour the project exists to demonstrate, end to end.

    The synthetic clip has hands for the first six seconds and none afterwards. Under
    adaptive weighting the hand channel's influence should fall away; under fixed weighting
    it should not, right up until there is no score left to weight at all.
    """
    results = run_both(tmp_path)
    both_hands = lambda r: [
        w["weight"] for w in r["windows"] if w["channel"] == "hands" and w["tStartS"] < 4
    ]
    one_hand = lambda r: [
        w["weight"] for w in r["windows"] if w["channel"] == "hands" and 6 <= w["tStartS"] < 9
    ]

    # With both hands visible the two agree: there is nothing to be cleverer about.
    assert all(abs(w - 1 / 3) < 0.002 for w in both_hands(results["adaptive"]) if w is not None)
    assert all(abs(w - 1 / 3) < 0.002 for w in both_hands(results["fixed"]) if w is not None)

    # With one hand gone, adaptive turns the channel down and fixed carries on regardless.
    adaptive_partial = [w for w in one_hand(results["adaptive"]) if w is not None]
    fixed_partial = [w for w in one_hand(results["fixed"]) if w is not None]
    assert adaptive_partial and max(adaptive_partial) < 1 / 3
    assert fixed_partial and all(abs(w - 1 / 3) < 0.002 for w in fixed_partial)
