"""The assembly line: a video goes in one end, finished feedback comes out the other.

Five stages, each handing its output to the next:

  extracting   pull frames out of the video at the analysis rate
  detecting    find face, body and hand landmarks in each frame
  analysing    turn windows of landmarks into a score per channel
  fusing       combine the three channel scores into one
  feedback     turn the run of scores into timestamped things worth saying

Keeping them in a line, rather than tangled together, is what makes the project's central
comparison possible. Only one object differs between an adaptive run and a fixed-weight run
of the same video, and it is passed in from outside. Nothing else in this file knows or
cares which is in use, so any difference between two runs comes from the weighting and
cannot have leaked in from anywhere else.

Detection is by far the slowest stage, so its output is written to a cache file as it goes.
Re-running the same video reuses that cache instead of detecting again, which turns a run
from minutes into seconds. Passing `reuse_cache=False` forces a fresh detection.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from analysers import FaceAnalyser, HandsAnalyser, PoseAnalyser, WINDOW_S, window_frames
from feedback import all_events, recommendations, summarise
from fusion import FusionStrategy
from serialisation.landmarks import (
    aspect_of,
    make_frame,
    make_header,
    read_frames,
    read_header,
    write_landmarks,
)
from serialisation.results import build_result, write_results

#: The five stage names reported to the progress display, in order.
STAGES = ("extracting", "detecting", "analysing", "fusing", "feedback")

ProgressFn = Callable[[str, int, int], None]


class Pipeline:
    """Runs one video through every stage and returns the finished result.

    The fusion strategy is injected rather than chosen here. That is the whole point: it is
    the single variable in the comparison, and this class is deliberately unaware of which
    one it was handed.
    """

    def __init__(self, fusion_strategy: FusionStrategy, window_s: float = WINDOW_S) -> None:
        self.fusion = fusion_strategy
        self.window_s = window_s

    # ------------------------------------------------------------------ stages 1 and 2

    def _landmark_cache(
        self,
        video_path: str,
        fps: float,
        cache_path: Path,
        reuse_cache: bool,
        on_progress: ProgressFn | None,
    ) -> Path:
        """Make sure a landmark cache exists for this video, detecting only if needed."""
        if reuse_cache and cache_path.exists():
            return cache_path

        # Imported here rather than at the top so that reading an existing cache, and the
        # self-test path, never require OpenCV or MediaPipe to be installed.
        from detection.holistic import HolisticDetector, mediapipe_version
        from frames.extractor import expected_sample_count, probe, sample_frames

        info = probe(video_path, fps)
        total = expected_sample_count(info)
        if on_progress:
            on_progress("extracting", total, total)

        header = make_header(
            video=Path(video_path).name,
            video_duration_s=info.duration_s,
            source_fps=info.source_fps,
            analysis_fps=info.analysis_fps,
            frame_width=info.width,
            frame_height=info.height,
            mediapipe_version=mediapipe_version(),
        )

        def records():
            with HolisticDetector() as detector:
                for n, frame in enumerate(sample_frames(video_path, fps), start=1):
                    if on_progress and (n == 1 or n == total or n % 5 == 0):
                        on_progress("detecting", n, total)
                    yield make_frame(frame.index, frame.t_s, detector.detect(frame.image))

        write_landmarks(cache_path, records(), header=header)
        return cache_path

    # ---------------------------------------------------------------------- the run

    def run(
        self,
        video_path: str,
        fps: float = 6.0,
        out_dir: str | None = None,
        on_progress: ProgressFn | None = None,
        reuse_cache: bool = True,
    ) -> dict:
        """Analyse one video and return the finished result.

        Also writes `landmarks.jsonl` and `results.json` into `out_dir` when one is given.
        Python stops at those two files; nothing here touches the database.
        """
        video = Path(video_path)
        directory = Path(out_dir) if out_dir else video.parent / "landmarks"
        cache = (
            directory / "landmarks.jsonl"
            if out_dir
            else directory / f"{video.stem}.landmarks.jsonl"
        )

        self._landmark_cache(str(video), fps, cache, reuse_cache, on_progress)

        header = read_header(cache)
        aspect = aspect_of(header)
        windows = list(window_frames(read_frames(cache), self.window_s))

        # Stage 3. One analyser per channel, each fed the windows in order, because two of
        # them remember things between windows.
        face = FaceAnalyser(aspect=aspect)
        pose = PoseAnalyser(aspect=aspect)
        hands = HandsAnalyser(aspect=aspect)

        total = len(windows)
        face_windows, pose_windows, hand_windows = [], [], []
        for n, window in enumerate(windows, start=1):
            face_windows.append(face.analyse_detail(window))
            pose_windows.append(pose.analyse_detail(window))
            hand_windows.append(hands.analyse_detail(window))
            if on_progress and (n == 1 or n == total or n % 10 == 0):
                on_progress("analysing", n, total)

        # Stage 4. The one line the whole project is about.
        self.fusion.reset()
        fused = []
        for n, (f, p, h) in enumerate(zip(face_windows, pose_windows, hand_windows), start=1):
            fused.append(
                self.fusion.fuse(
                    {"face": f.score, "pose": p.score, "hands": h.score},
                    {"face": f.visibility, "pose": p.visibility, "hands": h.visibility},
                )
            )
            if on_progress and (n == 1 or n == total or n % 10 == 0):
                on_progress("fusing", n, total)

        # Stage 5.
        if on_progress:
            on_progress("feedback", 1, 1)
        events = all_events(face_windows, pose_windows, hand_windows)
        channel_windows = {"face": face_windows, "pose": pose_windows, "hands": hand_windows}
        summary = summarise(
            [combined.score for combined in fused],
            channel_windows,
            events,
            header.get("videoDurationS", 0.0),
        )
        advice = recommendations(events, summary.channel_scores)

        result = build_result(
            fusion_mode=getattr(self.fusion, "name", "unknown"),
            fused=fused,
            channel_windows=channel_windows,
            summary=summary,
            events=events,
            recommendations=advice,
            analysis_fps=header.get("analysisFps", fps),
            window_s=self.window_s,
            fusion_params={
                "alpha": getattr(self.fusion, "alpha", None),
                "vFloor": getattr(self.fusion, "v_floor", None),
            },
            mediapipe_version=header.get("mediapipe", {}).get("version", "unknown"),
        )

        if out_dir:
            write_results(Path(out_dir) / "results.json", result)
        return result
