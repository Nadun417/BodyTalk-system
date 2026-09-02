"""Combining the face, pose and hand scores into one score per analysis window.

This package holds the part of BodyTalk the project is really about. There are
two ways of doing the combining and they can be exchanged for one another:

  AdaptiveFusion      weights each channel by how clearly it could be seen
  FixedWeightFusion   gives every channel an equal share regardless

Both follow the same interface, `FusionStrategy`, and `make_strategy` picks
between them using the mode stored on the session. Because the swap is the only
thing that changes between two runs of the same video, any difference in the
results can be put down to the weighting method rather than to some other part
of the code behaving differently.
"""

from .base import FusionResult, FusionStrategy
from .adaptive import AdaptiveFusion
from .fixed import FixedWeightFusion
from .factory import make_strategy

__all__ = ["FusionResult", "FusionStrategy", "AdaptiveFusion", "FixedWeightFusion", "make_strategy"]
