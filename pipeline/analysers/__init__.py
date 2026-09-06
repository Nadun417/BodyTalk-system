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
    MetricSpec,
    Window,
    metric_values,
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

#: What each channel measures, looked up by channel name.
#:
#: Assembled here rather than written out by hand so that the list can only ever come from
#: the analyser that actually does the measuring. Adding a measurement to an analyser
#: without it appearing in the saved results and the feedback would otherwise be an easy
#: mistake to make, and a silent one.
CHANNEL_METRICS = {
    analyser.channel: analyser.METRICS
    for analyser in (FaceAnalyser, PoseAnalyser, HandsAnalyser)
}

__all__ = [
    "WINDOW_S",
    "Analyser",
    "AnalysisResult",
    "CHANNEL_METRICS",
    "MetricSpec",
    "Window",
    "metric_values",
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
