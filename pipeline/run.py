"""The way the analysis pipeline is started. Everything begins here.

The desktop application launches this as a separate program rather than calling into it
directly. It reads the job it was given, works through the stages, and writes the results
into the session folder. It never goes near the database; the application picks the results
file up and handles all of that.

While it runs it prints status updates to standard output, one JSON object per line, which
is how the application knows what to show on the progress screen:

    {"type": "progress", "stage": "...", "done": N, "total": M}
    {"type": "result", "fusionMode": "...", "overallScore": ..., "windows": [...], "events": [...]}
    {"type": "error", "message": "..."}

There are two modes that exist to make development practical.

`--selftest` makes up plausible numbers instead of analysing anything, using nothing beyond
Python's own libraries. That means the whole path from this script through to the dashboard
can be tried out before MediaPipe is even installed. It is not a complete fake, though: the
weighting and combining are done by the real fusion code, so that part is genuinely being
exercised rather than simulated.

`--detect-only` runs just the slow half, pulling frames out of the video and detecting
landmarks in them, then saves everything to a file and stops. The later stages are then
built against that saved file rather than sitting through detection again after every
change:

    pipeline/.venv/Scripts/python.exe pipeline/run.py --detect-only \
        --video "fixtures/Medium quality.mp4"
"""

from __future__ import annotations

import argparse
import json
import sys

from fusion import make_strategy


def emit(obj: dict) -> None:
    """Write one compact JSON event to stdout and flush immediately."""
    sys.stdout.write(json.dumps(obj, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def run_selftest(session_id: int, fusion_mode: str) -> dict:
    """Make up a minute's worth of analysis so the rest of the app can be tried out.

    The hands are deliberately made to disappear between 0:30 and 0:45. That is the whole
    point of the simulation: it produces a stretch where adaptive weighting visibly does
    something, with the hand channel's influence dropping away to nothing and the other two
    taking over. Without a gap like that, both fusion modes would look identical.

    The scores themselves are random, but the weighting and combining are done by the real
    fusion code rather than faked, so that part is actually being tested.
    """
    import random

    random.seed(session_id or 42)
    strategy = make_strategy(fusion_mode)
    channels = ["face", "pose", "hands"]
    total = 12  # 12 windows × 5s = 60s
    windows: list[dict] = []

    for i in range(total):
        emit({"type": "progress", "stage": "analysing", "done": i + 1, "total": total})
        t0, t1 = i * 5.0, i * 5.0 + 5.0

        visibility = {
            "face": round(random.uniform(0.80, 0.98), 3),
            "pose": round(random.uniform(0.70, 0.95), 3),
            "hands": 0.0 if 6 <= i <= 8 else round(random.uniform(0.50, 0.90), 3),
        }
        raw = {ch: round(random.uniform(55, 90), 1) for ch in channels}

        weights = strategy.weights(visibility)
        fused = strategy.fuse(raw, visibility)

        for ch in channels:
            windows.append(
                {
                    "tStartS": t0,
                    "tEndS": t1,
                    "channel": ch,
                    "rawScore": raw[ch],
                    "visibility": visibility[ch],
                    "weight": round(weights[ch], 3),
                }
            )
        windows.append(
            {
                "tStartS": t0,
                "tEndS": t1,
                "channel": "fused",
                "rawScore": round(fused, 1),
                "visibility": None,
                "weight": None,
            }
        )

    events = [
        {
            "tStartS": 30.0,
            "tEndS": 45.0,
            "channel": "hands",
            "type": "out_of_frame",
            "severity": "info",
            "message": "Hands left the frame 0:30–0:45.",
            "suggestion": "Keep your hands visible so natural gestures come through.",
        },
        {
            "tStartS": 10.0,
            "tEndS": 25.0,
            "channel": "pose",
            "type": "forward_lean",
            "severity": "medium",
            "message": "You leaned forward 0:10–0:25.",
            "suggestion": "Sit back a little and keep your shoulders level.",
        },
    ]

    fused_scores = [w["rawScore"] for w in windows if w["channel"] == "fused"]
    overall = round(sum(fused_scores) / len(fused_scores), 1)
    return {
        "type": "result",
        "fusionMode": fusion_mode,
        "overallScore": overall,
        "windows": windows,
        "events": events,
    }


def run_detect_only(args: argparse.Namespace) -> dict:
    """Run the slow half once and save the result to a file.

    Pulls frames out of the video, detects landmarks in each one, writes them all out, and
    stops there. No scoring, no combining, no feedback. Those stages read the file this
    produces rather than doing detection themselves.

    The imports sit inside the function rather than at the top of the file on purpose. It
    means `--selftest` never loads OpenCV or MediaPipe, so it still works on a machine where
    neither is installed.
    """
    import time
    from pathlib import Path

    from detection.holistic import HolisticDetector, mediapipe_version
    from frames.extractor import expected_sample_count, probe, sample_frames
    from serialisation.landmarks import make_frame, make_header, write_landmarks

    if not args.video:
        raise ValueError("--detect-only needs --video pointing at a clip")

    video = Path(args.video)
    if not video.exists():
        raise ValueError(f"Video not found: {video}")

    info = probe(str(video), args.fps)
    total = expected_sample_count(info)
    if args.max_frames:
        total = min(total, args.max_frames) if total else args.max_frames

    out = (
        Path(args.out)
        if args.out
        else Path("fixtures/landmarks") / f"{video.stem}.landmarks.jsonl"
    )

    header = make_header(
        video=video.name,
        video_duration_s=info.duration_s,
        source_fps=info.source_fps,
        analysis_fps=info.analysis_fps,
        frame_width=info.width,
        frame_height=info.height,
        mediapipe_version=mediapipe_version(),
        refine_face_landmarks=False,
    )

    found = {"face": 0, "pose": 0, "leftHand": 0, "rightHand": 0}
    inference_s = 0.0

    def records():
        """Detect one frame at a time and pass each result straight to the writer.

        Written as a generator so that a long clip is never held in memory all at once.
        Each frame is dealt with and let go of before the next one is loaded.
        """
        nonlocal inference_s
        with HolisticDetector(model_complexity=args.complexity) as detector:
            frames = sample_frames(str(video), args.fps, args.max_frames)
            for n, frame in enumerate(frames, start=1):
                t0 = time.perf_counter()
                channels = detector.detect(frame.image)
                inference_s += time.perf_counter() - t0

                for channel, slot in channels.items():
                    if slot["detected"]:
                        found[channel] += 1

                # Only report every fifth frame, plus the first and the last. Reporting
                # every single one would scroll thousands of lines past in a terminal, and
                # this is still often enough for the progress bar to move smoothly.
                if n == 1 or n == total or n % 5 == 0:
                    emit({"type": "progress", "stage": "detecting", "done": n, "total": total})

                yield make_frame(frame.index, frame.t_s, channels)

    wall_start = time.perf_counter()
    written = write_landmarks(out, records(), header=header)
    wall_s = time.perf_counter() - wall_start

    if written == 0:
        raise ValueError(f"No frames could be sampled from {video} — is it readable?")

    return {
        "type": "result",
        "stage": "detect-only",
        "video": str(video),
        "out": str(out),
        "framesWritten": written,
        "analysisFps": round(info.analysis_fps, 2),
        "durationS": round(info.duration_s, 1),
        "detectionRatePct": {
            channel: round(100.0 * count / written, 1) for channel, count in found.items()
        },
        "msPerFrame": round(1000.0 * inference_s / written, 1),
        "wallS": round(wall_s, 1),
        "ratioToRealTime": round(wall_s / info.duration_s, 2) if info.duration_s else None,
    }


def run_pipeline(args: argparse.Namespace) -> dict:
    """Real pipeline: extraction → detection → analysers → fusion → feedback.
    Steps 3-5 fill this in; until then use --detect-only to build the cache."""
    raise NotImplementedError(
        "Scoring, weighting and feedback are not written yet. "
        "Use --detect-only to save the landmarks, or --selftest for the simulated run."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="BodyTalk analysis pipeline")
    parser.add_argument("--session-id", type=int, default=0)
    parser.add_argument("--fusion", choices=["adaptive", "fixed"], default="adaptive")
    parser.add_argument("--video", type=str, default=None)
    parser.add_argument("--fps", type=float, default=6.0)
    parser.add_argument("--out", type=str, default=None)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument(
        "--detect-only",
        action="store_true",
        help="only pull out frames and detect landmarks, saving them to landmarks.jsonl",
    )
    parser.add_argument(
        "--complexity",
        type=int,
        default=1,
        choices=[0, 1, 2],
        help="MediaPipe model_complexity: 0 fastest, 2 most accurate (default 1)",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=0,
        help="stop after N sampled frames (0 = whole video); handy for quick checks",
    )
    args = parser.parse_args()

    try:
        if args.selftest:
            result = run_selftest(args.session_id, args.fusion)
        elif args.detect_only:
            result = run_detect_only(args)
        else:
            result = run_pipeline(args)
    except Exception as exc:  # noqa: BLE001 — surface any failure as a clean error event
        emit({"type": "error", "message": str(exc)})
        return 1

    emit(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
