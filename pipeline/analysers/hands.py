"""Hand and gesture channel. Not written yet.

MediaPipe reports 21 landmarks for each hand, so 42 in total when both are in shot.

Planned measurements, with the exact thresholds still to be settled against real footage:

  gesture activity      how far the hands travel, aiming for a natural middle ground
                        rather than treating more movement as automatically better
  fidgeting             small repeated back-and-forth movements
  hand to face          how often the hands come up to touch the face
  time in frame         how much of the window the hands were visible for at all

That last one is the clearest case for weighting channels by visibility. Hands leave the
shot constantly in practice videos, usually because the person is sitting at a desk with a
laptop camera pointed at their upper body. When that happens there is genuinely no
evidence about their gestures, and scoring them anyway would mean marking someone down
for something the camera never captured.

Because of that, this channel has to keep two ideas apart: hands that were visible and
barely moved, and hands that were never visible in the first place. Those look identical
if you only measure movement, but they mean completely different things.
"""

from __future__ import annotations

from .base import Analyser, AnalysisResult


class HandsAnalyser(Analyser):
    channel = "hands"

    def analyse(self, window: list) -> AnalysisResult:
        raise NotImplementedError("Hands analyser is implemented during the Channel Analysers task.")
