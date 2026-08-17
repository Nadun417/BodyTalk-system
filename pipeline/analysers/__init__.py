"""The three behavioural channels BodyTalk measures separately.

Each analyser takes a window of landmarks and returns a score from 0 to 100 for its own
channel, along with how clearly that channel could be seen. They all follow the same
`Analyser` interface, so the fusion stage can work through them in a loop rather than
having a separate branch for each one.
"""

from .base import (
    WINDOW_S,
    Analyser,
    AnalysisResult,
    Window,
    dist,
    presence_rate,
    scale,
    spread,
    square,
    window_frames,
)
from .face import FaceAnalyser
from .pose import PoseAnalyser
from .hands import HandsAnalyser

__all__ = [
    "WINDOW_S",
    "Analyser",
    "AnalysisResult",
    "Window",
    "window_frames",
    "scale",
    "dist",
    "spread",
    "square",
    "presence_rate",
    "FaceAnalyser",
    "PoseAnalyser",
    "HandsAnalyser",
]
