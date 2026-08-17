"""Body posture channel. Not written yet.

MediaPipe reports 33 body keypoints, and unlike the face and hands it gives a real
visibility number for each one, so this is the only channel that can measure how well it
was seen directly rather than falling back on how often it was detected.

Planned measurements, with the exact thresholds still to be settled against real footage:

  posture uprightness   the angle the head and shoulders lean away from vertical
  shoulder levelness    how much higher one shoulder sits than the other
  body sway             how much the upper body drifts from side to side

Only the upper body is used. Practice videos are usually recorded on a laptop or phone
propped up on a desk, which crops everything below the chest, so anything depending on
hip position would fail on most real recordings.
"""

from __future__ import annotations

from .base import Analyser, AnalysisResult


class PoseAnalyser(Analyser):
    channel = "pose"

    def analyse(self, window: list) -> AnalysisResult:
        raise NotImplementedError("Pose analyser is implemented during the Channel Analysers task.")
