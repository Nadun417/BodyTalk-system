"""Boiling the whole run down to the headline numbers the dashboard shows.

The analysers produce a score for every channel for every second of video, which is far
too much detail to put in front of someone. This reduces all of that to one overall score
for the session plus one score per channel, so the user can see at a glance whether it
was their posture or their gestures that let them down.
"""

from __future__ import annotations


def score_session(window_scores: list[dict]) -> dict:
    """Return {"overallScore": float, "perChannel": {channel: float}}."""
    raise NotImplementedError("Scorer is implemented during the Feedback Engine task.")
