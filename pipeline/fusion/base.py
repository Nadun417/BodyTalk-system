"""The shared interface that both ways of combining channel scores must follow.

BodyTalk analyses three things separately: the face, the body pose and the hands.
Each one produces its own score for a slice of the video. Something then has to
turn those three numbers into one. There are two ways of doing that in this
project, and the whole point of the comparison is that they can be swapped for
one another without changing anything else in the pipeline.

Keeping them behind one interface is what makes the comparison fair. When the
only thing that differs between two runs is which class is plugged in here, any
difference in the results has to come from the weighting method itself, not from
some other part of the code having changed as well.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class FusionStrategy(ABC):
    """Combines the per-channel scores for one analysis window into a single score.

    Both arguments are dictionaries keyed by channel name, normally
    "face", "pose" and "hands":

      scores      how well that channel scored, 0 to 100
      visibility  how clearly the camera could see that channel, 0 to 1

    Subclasses only have to implement `weights`. The `fuse` method below is the
    same for every strategy, so it is written once here.

    `weights` is deliberately a public method rather than something hidden
    inside `fuse`. The weight each channel was given has to be saved for every
    window, because it is what the weight-over-time chart is drawn from and what
    the evaluation compares. Working it out again afterwards would be guesswork.
    """

    @abstractmethod
    def weights(self, visibility: dict[str, float]) -> dict[str, float]:
        """Work out how much each channel should count for.

        The returned weights should add up to 1 across the channels that are
        present, so the fused score stays on the same 0 to 100 scale as the
        channel scores that went into it.
        """

    def fuse(self, scores: dict[str, float], visibility: dict[str, float]) -> float:
        """Multiply each channel's score by its weight and add the results together."""
        w = self.weights(visibility)
        return sum(w.get(ch, 0.0) * scores.get(ch, 0.0) for ch in scores)
