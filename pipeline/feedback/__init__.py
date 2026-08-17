"""Turning the run of scores into something worth reading.

Two separate jobs live here. `score_session` boils the whole video down to an overall
score and one score per channel. `derive_events` looks for stretches where something
noticeable was happening and turns each one into a timestamped comment the user can jump
straight to in their video.
"""

from .scorer import score_session
from .rules import derive_events

__all__ = ["score_session", "derive_events"]
