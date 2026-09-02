"""Weighting each channel by how clearly it could actually be seen.

This is the idea the project is testing. Every channel produces a score and, alongside it,
a measure of how well that channel could be seen. Rather than trusting all three equally,
a channel that could barely be seen is given proportionally less say, so a hand that left
the frame stops dragging the verdict around instead of continuing to vote on it.

Three steps, in this order, and the order matters:

  1. Smooth the visibility, so the weights do not lurch about from window to window.
  2. Drop any channel still below the floor, because a barely-seen channel voting at all
     is worse than it not voting.
  3. Share the remaining influence out in proportion, so the weights always total one.

Smoothing comes first deliberately. If the floor were applied to the raw values instead, a
single bad second could knock a channel out of the reckoning and let it back in immediately
afterwards, and the weights would flicker. Smoothing first means a channel has to be
genuinely unclear for a moment or two before it loses its say.

What the smoothing does is blend each new reading into a running average, so recent windows
count for more than older ones without the older ones being thrown away. At the default
setting each new window is 60 per cent of the answer and everything before it makes up the
remaining 40 per cent, which works out at a memory of roughly two seconds.

**The first window has nothing to average against**, and what to do about that was an open
question for a while. The design can be read as saying the running average starts at the
floor value. It does not start there, and starting there would understate every channel for
the opening seconds of every video: a channel plainly visible at 0.90 would be recorded as
0.62, and a channel genuinely visible at 0.15 would be pushed up to 0.17 and excluded
outright, purely because of where the average was told to begin. The opening seconds of a
practice interview are not a throwaway period, so a distortion concentrated exactly there
would be a poor thing to carry into the results. The first window therefore uses precisely
what was measured, and smoothing begins from the second window onward, which is what a
running average needs in any case.
"""

from __future__ import annotations

from .base import FusionResult, FusionStrategy


class AdaptiveFusion(FusionStrategy):
    """Weights each channel by its smoothed visibility.

    Both settings are constructor arguments so the evaluation can sweep them and report how
    sensitive the results are to the choice, rather than presenting two numbers as though
    they were self-evident.
    """

    name = "adaptive"

    def __init__(self, alpha: float = 0.6, v_floor: float = 0.2) -> None:
        self.alpha = alpha
        self.v_floor = v_floor
        #: the running average of visibility, one entry per channel
        self._smoothed: dict[str, float] = {}

    def reset(self) -> None:
        self._smoothed.clear()

    def fuse(
        self,
        scores: dict[str, float | None],
        visibility: dict[str, float],
    ) -> FusionResult:
        channels = list(scores)

        # A channel with no score could not be measured, so it has nothing to contribute
        # whatever the camera saw. Treating its visibility as zero lets the rest of the
        # calculation handle it with no special case, and lets the running average fade it
        # out gently rather than dropping it like a stone.
        measured = {
            channel: (visibility.get(channel, 0.0) if scores.get(channel) is not None else 0.0)
            for channel in channels
        }

        for channel, value in measured.items():
            previous = self._smoothed.get(channel)
            if previous is None:
                self._smoothed[channel] = value
            else:
                self._smoothed[channel] = self.alpha * value + (1.0 - self.alpha) * previous
        smoothed = {channel: self._smoothed[channel] for channel in channels}

        # Two ways to end up with no say: too unclear to trust, or nothing to say. The
        # second is easy to miss, because the running average keeps a channel alive for a
        # window or two after it stops producing a score. Left in, it would be handed a
        # share of the weighting it cannot use, the shares of the channels that did score
        # would no longer total one, and the combined score would come out silently low
        # in the window right after a dropout.
        surviving = {
            channel: (
                value
                if value >= self.v_floor and scores.get(channel) is not None
                else 0.0
            )
            for channel, value in smoothed.items()
        }

        total = sum(surviving.values())
        if total <= 0:
            # Nothing was seen clearly enough to justify a number. Saying so is the honest
            # answer; inventing one out of channels we have just declared unreliable is not.
            # The dashboard shows a gap here and the feedback rules skip the window.
            return FusionResult(
                score=None,
                weights={channel: None for channel in channels},
                smoothed_visibility=smoothed,
            )

        weights = {channel: value / total for channel, value in surviving.items()}
        score = sum(
            weights[channel] * scores[channel]
            for channel in channels
            if scores.get(channel) is not None
        )
        return FusionResult(score=score, weights=weights, smoothed_visibility=smoothed)
