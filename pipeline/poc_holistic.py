"""
A throwaway script for checking one assumption before building anything on top of it.
Not part of the application.

The question it answers is the one the whole project depends on: does MediaPipe actually
report how clearly it could see each landmark?

That matters because the adaptive weighting works by giving each channel a say in
proportion to how well it could be seen. If a channel reports nothing about its own
visibility, there is no honest way to weight it and something else has to stand in. Rather
than assume, this script runs over real footage and reports which channels give what.

It also times how long each frame takes, which is what settles how many frames a second
are worth analysing.

Run it:
    pipeline/.venv/Scripts/python.exe pipeline/poc_holistic.py --video fixtures/my_clip.mp4
    pipeline/.venv/Scripts/python.exe pipeline/poc_holistic.py --video fixtures/my_clip.mp4 --fps 10

Deliberately one ugly file: no classes, no imports from the real pipeline. Ignore or delete later.
"""

import argparse
import statistics
import sys
import time

import cv2
import mediapipe as mp

mp_holistic = mp.solutions.holistic


def describe(values):
    """min / mean / max of a list, or a dash when there's nothing to describe."""
    if not values:
        return "          -           "
    return f"{min(values):.3f} / {statistics.fmean(values):.3f} / {max(values):.3f}"


def main():
    ap = argparse.ArgumentParser(description="MediaPipe Holistic check")
    ap.add_argument("--video", required=True, help="path to a practice clip")
    ap.add_argument(
        "--fps",
        type=float,
        default=6.0,
        help="analysis sampling rate; frames between samples are skipped (default 6)",
    )
    ap.add_argument(
        "--max-frames",
        type=int,
        default=0,
        help="stop after N sampled frames (0 = whole video)",
    )
    ap.add_argument(
        "--print-every",
        type=int,
        default=10,
        help="print a per-frame line every N sampled frames (default 10)",
    )
    ap.add_argument(
        "--complexity",
        type=int,
        default=1,
        choices=[0, 1, 2],
        help="MediaPipe model_complexity: 0 fastest, 2 most accurate (default 1)",
    )
    args = ap.parse_args()

    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        sys.exit(f"Could not open video: {args.video}")

    source_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    duration_s = total_frames / source_fps if source_fps else 0.0

    # Sample every Nth frame to hit the requested analysis fps.
    stride = max(1, round(source_fps / args.fps))
    effective_fps = source_fps / stride

    print(f"\nVideo    : {args.video}")
    print(f"           {width}x{height}, {source_fps:.2f} fps source, {duration_s:.1f}s, {total_frames} frames")
    print(f"Sampling : every {stride} frame(s) -> {effective_fps:.2f} fps analysed (asked for {args.fps})")
    print(f"Model    : model_complexity={args.complexity}, refine_face_landmarks=False\n")

    # Counters for the summary.
    sampled = 0
    detected = {"face": 0, "pose": 0, "left_hand": 0, "right_hand": 0}
    counts = {"face": None, "pose": None, "left_hand": None, "right_hand": None}
    # Every per-landmark visibility/presence value we see, per channel.
    vis = {"face": [], "pose": [], "left_hand": [], "right_hand": []}
    pres = {"face": [], "pose": [], "left_hand": [], "right_hand": []}
    frame_times = []

    holistic = mp_holistic.Holistic(
        static_image_mode=False,  # video mode: MediaPipe tracks between frames
        model_complexity=args.complexity,
        refine_face_landmarks=False,  # 468 face landmarks, not 478 (per the pinned data contract)
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
    )

    frame_index = -1
    load_start = time.perf_counter()

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frame_index += 1
        if frame_index % stride != 0:
            continue  # skipped by sampling

        # Classic pitfall: OpenCV decodes to BGR, MediaPipe expects RGB.
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        rgb.flags.writeable = False

        t0 = time.perf_counter()
        results = holistic.process(rgb)
        frame_times.append(time.perf_counter() - t0)

        sampled += 1
        t_s = frame_index / source_fps

        channels = {
            "face": results.face_landmarks,
            "pose": results.pose_landmarks,
            "left_hand": results.left_hand_landmarks,
            "right_hand": results.right_hand_landmarks,
        }

        for name, landmark_list in channels.items():
            if landmark_list is None:
                continue
            detected[name] += 1
            counts[name] = len(landmark_list.landmark)
            for lm in landmark_list.landmark:
                # Both fields always EXIST on the protobuf. The real question is
                # whether they carry a meaningful value or a hardcoded 0.0.
                vis[name].append(lm.visibility)
                pres[name].append(lm.presence)

        if sampled == 1 or sampled % args.print_every == 0:
            pose_vis = (
                [lm.visibility for lm in results.pose_landmarks.landmark]
                if results.pose_landmarks
                else []
            )
            found = "".join(
                letter if channels[name] is not None else "-"
                for name, letter in (
                    ("face", "F"),
                    ("pose", "P"),
                    ("left_hand", "L"),
                    ("right_hand", "R"),
                )
            )
            pose_summary = (
                f"pose vis min/mean/max {describe(pose_vis)}" if pose_vis else "pose not detected"
            )
            print(f"  t={t_s:6.2f}s  frame {frame_index:5d}  [{found}]  {pose_summary}")

        if args.max_frames and sampled >= args.max_frames:
            break

    holistic.close()
    cap.release()
    wall_s = time.perf_counter() - load_start

    if sampled == 0:
        sys.exit("No frames were sampled - is the video readable?")

    # ---------------------------------------------------------------- summary
    print("\n" + "=" * 78)
    print("DETECTION RATE  (how often each channel was found at all)")
    print("=" * 78)
    for name in ("face", "pose", "left_hand", "right_hand"):
        pct = 100.0 * detected[name] / sampled
        n = counts[name] if counts[name] is not None else 0
        print(f"  {name:<11} {detected[name]:5d}/{sampled} frames ({pct:5.1f}%)   {n} landmarks each")

    print("\n" + "=" * 78)
    print("THE R1 CHECK - per-landmark reliability signal, by channel")
    print("=" * 78)
    print(f"  {'channel':<11} {'visibility min/mean/max':<26} {'presence min/mean/max':<26} verdict")
    for name in ("face", "pose", "left_hand", "right_hand"):
        v, p = vis[name], pres[name]
        # A channel whose values never move off 0.0 is a placeholder, not a signal.
        v_real = bool(v) and max(v) > 0.0
        p_real = bool(p) and max(p) > 0.0
        if v_real:
            verdict = "REAL visibility -> use directly"
        elif p_real:
            verdict = "presence only"
        elif v:
            verdict = "all zero -> need a proxy"
        else:
            verdict = "never detected"
        print(f"  {name:<11} {describe(v):<26} {describe(p):<26} {verdict}")

    print("\n" + "=" * 78)
    print("TIMING  (how many frames a second can this laptop afford?)")
    print("=" * 78)
    per_frame_ms = statistics.fmean(frame_times) * 1000
    median_ms = statistics.median(frame_times) * 1000
    analysed_span_s = sampled / effective_fps
    print(f"  sampled frames        : {sampled}")
    print(f"  inference per frame   : {per_frame_ms:.1f} ms mean, {median_ms:.1f} ms median")
    print(f"  total wall time       : {wall_s:.1f}s for {analysed_span_s:.1f}s of video")
    if analysed_span_s > 0:
        ratio = wall_s / analysed_span_s
        budget = "within" if ratio <= 3.0 else "OVER"
        print(f"  processing ratio      : {ratio:.2f}x real time  ({budget} the ~2-3x target)")
    print(f"  max sustainable fps   : {1000 / per_frame_ms:.1f} fps (inference alone, 1.0x real time)")
    print()


if __name__ == "__main__":
    main()
