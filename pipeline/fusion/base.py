"""The interface both ways of combining channel scores share.

This is where the project earns its keep. Everything before this point measures things;
this is the part that decides how much each measurement counts. There are two ways of
doing it and they are interchangeable, so a video can be analysed twice with nothing
different between the runs except which of these objects was used. Any difference in the
results is therefore attributable to the weighting method and to nothing else, which is
what makes the comparison worth reporting at all.

One call, not two. An earlier version offered the weights and the combined score as
separate methods, which cannot work here: the adaptive strategy carries a running average
from one window to the next, so asking it for the weights and then asking it to combine
would advance that average twice and quietly corrupt every window after the first. A
single call returning both removes the possibility.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class FusionResult:
    """One window combined, together with the working-out behind it.

    The weights are not a debugging extra. They are the record of how much each channel
    was allowed to influence the result, they are saved for every window, and they are
    what the weight-over-time chart draws. Without them the comparison would be an
    assertion rather than a demonstration.
    """

    score: float | None
    weights: dict[str, float | None]
    #: what the adaptive strategy smoothed the visibility to; empty for fixed weighting
    smoothed_visibility: dict[str, float] = field(default_factory=dict)


class FusionStrategy(ABC):
    """Combines the per-channel scores for one window into a single score.

    Windows arrive in order, one at a time, because a strategy is allowed to remember what
    came before. Analysing a second video means either a fresh object or a call to
    `reset()`, otherwise the end of one recording bleeds into the start of the next.
    """

    #: the name stored on the session, so a saved result says how it was produced
    name: str

    @abstractmethod
    def fuse(
        self,
        scores: dict[str, float | None],
        visibility: dict[str, float],
    ) -> FusionResult:
        """Combine one window.

        A channel whose score is None could not be measured at all in this window. It
        takes no part in the result, whichever strategy is running.
        """

    def reset(self) -> None:
        """Forget anything carried between windows. Called between videos."""
