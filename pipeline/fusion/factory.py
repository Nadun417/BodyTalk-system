"""Turns the session's chosen mode into the matching fusion object."""

from __future__ import annotations

from .base import FusionStrategy
from .adaptive import AdaptiveFusion
from .fixed import FixedWeightFusion


def make_strategy(fusion_mode: str) -> FusionStrategy:
    """Return the fusion strategy that matches the mode saved on the session.

    Every session records which mode it was analysed with, so this is the one
    place that turns that stored text into an actual object. Keeping the choice
    here means the rest of the pipeline never has to know which mode is running,
    and analysing the same video both ways is just two runs with a different
    string passed in.

    An unknown mode raises rather than quietly falling back to a default. A typo
    that silently produced adaptive results while the session claimed to be
    fixed would ruin the comparison, and it would be very hard to spot later.
    """
    if fusion_mode == "adaptive":
        return AdaptiveFusion()
    if fusion_mode == "fixed":
        return FixedWeightFusion()
    raise ValueError(f"Unknown fusion_mode: {fusion_mode!r}")
