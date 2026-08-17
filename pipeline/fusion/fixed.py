"""The comparison baseline: fixed weights that ignore how visible anything was."""

from __future__ import annotations

from .base import FusionStrategy


class FixedWeightFusion(FusionStrategy):
    """Gives every channel the same say, no matter what the camera could see.

    This exists to be compared against, not because it is the better method.
    Claiming that adaptive weighting helps is only worth anything if there is
    something to measure it against, so the same pipeline runs a second time
    with the weighting logic swapped out for this, and the two sets of results
    are put side by side.

    By default each channel gets an equal share. With three channels that is a
    third each. If the hands are out of shot for a minute, they still get their
    third, and that is the point: the score for that minute is partly built on
    evidence that was never actually recorded. Showing that happening is what
    makes the case for the adaptive version.

    `weights_override` lets a different fixed split be passed in, for instance
    if a later experiment wants to try weightings taken from published work
    rather than an even split. Nothing uses it yet.
    """

    def __init__(self, weights_override: dict[str, float] | None = None) -> None:
        self._override = weights_override

    def weights(self, visibility: dict[str, float]) -> dict[str, float]:
        if self._override:
            return dict(self._override)
        # Note that `visibility` is accepted and then deliberately not read.
        # Only the number of channels matters here. Keeping the argument means
        # this class still fits the shared interface and can be swapped in for
        # the adaptive version without anything else changing.
        n = len(visibility) or 1
        return {ch: 1.0 / n for ch in visibility}
