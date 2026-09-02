"""Giving every channel an equal say, whatever the camera actually saw.

This is the comparison the adaptive method has to beat, and it has to be built properly for
that comparison to mean anything. It is not a lesser implementation or a fallback: it is
the control, and the whole argument rests on it being a fair one.

It ignores visibility completely. That is the entire point. Whether a hand was in full view
or half out of the frame, as long as a score came back it counts for exactly as much as the
other channels.

There is one honest subtlety worth stating plainly, because it decides what the comparison
actually measures. When a channel produces **no score at all** there is no number to
average, and the equal shares are redistributed among the channels that do have one.
Without that, an absent channel would drag the result toward zero and the baseline would be
broken arithmetic rather than a fair alternative, which would make it easy to beat and
worthless as evidence.

So the baseline is naive about *reliability*, not about *availability*. Both methods cope
with a channel that is missing entirely. They differ over a channel that is present but
poorly seen, where this one keeps trusting it at full strength and the adaptive one turns it
down. That is where any difference between them comes from, and it is the right place for
it to come from.
"""

from __future__ import annotations

from .base import FusionResult, FusionStrategy


class FixedWeightFusion(FusionStrategy):
    """Equal weighting, or any other fixed split passed in.

    Holds nothing between windows: the weights depend on nothing that happened earlier,
    which is exactly what makes it the control.
    """

    name = "fixed"

    def __init__(self, weights_override: dict[str, float] | None = None) -> None:
        #: an alternative fixed split, for a second baseline drawn from the literature
        self._override = weights_override

    def fuse(
        self,
        scores: dict[str, float | None],
        visibility: dict[str, float],
    ) -> FusionResult:
        channels = list(scores)
        present = [channel for channel in channels if scores.get(channel) is not None]

        if not present:
            return FusionResult(
                score=None,
                weights={channel: None for channel in channels},
            )

        if self._override:
            shares = {channel: self._override.get(channel, 0.0) for channel in present}
            total = sum(shares.values()) or 1.0
            weights = {channel: share / total for channel, share in shares.items()}
        else:
            weights = {channel: 1.0 / len(present) for channel in present}

        full = {channel: weights.get(channel, 0.0) for channel in channels}
        score = sum(full[channel] * scores[channel] for channel in present)
        return FusionResult(score=score, weights=full)
