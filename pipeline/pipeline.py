"""Runs the analysis stages one after another and passes the results along.

The video goes through the same sequence every time. Frames are pulled out of it,
landmarks are detected in those frames, each channel analyses the landmarks, the channel
scores are combined, and finally the combined scores are turned into feedback. Each stage
only knows about the shape of what it receives and what it hands on, so any one of them
can be reworked without disturbing the others.

The fusion strategy is handed in rather than chosen here, which is what makes analysing
the same video with adaptive and with fixed weighting a matter of constructing this class
twice with a different object, changing nothing else.
"""

from __future__ import annotations

from typing import Callable

from fusion import FusionStrategy
from analysers import Analyser


class Pipeline:
    def __init__(self, fusion_strategy: FusionStrategy, analysers: list[Analyser]) -> None:
        self.fusion = fusion_strategy
        self.analysers = analysers

    def run(
        self,
        video_path: str,
        fps: float,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> dict:
        """Run every stage and return the finished result as a dictionary.

        `on_progress` is called as the work goes along so the desktop app can move its
        progress bar instead of sitting frozen while a long video is processed.
        """
        raise NotImplementedError(
            "The full pipeline is not connected up yet. Use run.py --detect-only to "
            "produce landmarks, or run.py --selftest for the simulated path."
        )
