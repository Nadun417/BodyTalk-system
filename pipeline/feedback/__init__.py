"""Turning the run of scores into things worth saying to the person who recorded the video.

Two steps, kept apart on purpose.

  rules.py   decides WHAT is worth saying, and when it happened
  scorer.py  reduces the whole session to the headline numbers and a short summary

The separation matters more than it looks. The rules own every judgement: which behaviours
count, how long they must last, and what is said about them. Anything added later that
rewords the output can only ever reword what the rules already found, so it cannot invent a
behaviour, move a timestamp, or reach a conclusion of its own.
"""

from .rules import (
    Event,
    Recommendation,
    all_events,
    clock,
    face_events,
    hand_events,
    pose_events,
    recommendations,
    sustained_intervals,
)
from .scorer import SessionFacts, SessionSummary, summarise, summary_sentence

__all__ = [
    "Event",
    "Recommendation",
    "all_events",
    "clock",
    "face_events",
    "hand_events",
    "pose_events",
    "recommendations",
    "sustained_intervals",
    "SessionFacts",
    "SessionSummary",
    "summarise",
    "summary_sentence",
]
