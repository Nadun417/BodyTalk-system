"""Reducing a whole session to the few numbers and sentences shown at the top.

The dashboard opens with one overall figure and one per channel, and the report opens with
a sentence or two of summary. This file produces those from the run of per-window results.

Two decisions worth stating, because both could reasonably have gone the other way.

**Windows with no score are left out rather than counted as zero.** A stretch where nothing
could be seen is missing evidence, not bad body language, and averaging zeros into the total
would quietly punish somebody for their camera framing. The count of skipped windows is
reported alongside, so a session built on very little evidence can be recognised as such
rather than presented with false confidence.

**The overall figure is the average of the already-combined window scores**, not a fresh
average of the three channels. The combining step has already decided how much each channel
deserved to count in each window, and averaging the channels again afterwards would throw
that away and hand every channel equal weight after all, which is the very thing the
adaptive method exists to avoid.
"""

from __future__ import annotations

import statistics as stats
from dataclasses import dataclass, field
from typing import Sequence

from .rules import Event, clock


@dataclass
class SessionFacts:
    """Plain counts about the session, for the summary and the phrasing step later.

    Only things that were counted. Nothing inferred, and nothing about the person.
    """

    duration_s: float
    windows_total: int
    windows_scored: int
    windows_skipped: int
    events_by_severity: dict[str, int] = field(default_factory=dict)
    events_by_channel: dict[str, int] = field(default_factory=dict)
    seconds_by_channel: dict[str, float] = field(default_factory=dict)
    strongest_channel: str | None = None
    weakest_channel: str | None = None
    positive_moments: int = 0


@dataclass
class SessionSummary:
    """Everything the top of the dashboard needs."""

    overall_score: float | None
    channel_scores: dict[str, float | None]
    facts: SessionFacts
    summary_text: str


def mean_or_none(values: Sequence[float | None]) -> float | None:
    """Average the values that exist. Returns None if none of them do."""
    present = [v for v in values if v is not None]
    return stats.fmean(present) if present else None


def summarise(
    fused_scores: Sequence[float | None],
    channel_windows: dict[str, Sequence],
    events: Sequence[Event],
    duration_s: float,
) -> SessionSummary:
    """Reduce a finished analysis to its headline numbers and a plain summary sentence."""
    overall = mean_or_none(fused_scores)
    channel_scores = {
        channel: mean_or_none([w.score for w in windows])
        for channel, windows in channel_windows.items()
    }

    scored = sum(1 for s in fused_scores if s is not None)
    facts = SessionFacts(
        duration_s=duration_s,
        windows_total=len(fused_scores),
        windows_scored=scored,
        windows_skipped=len(fused_scores) - scored,
    )

    for event in events:
        facts.events_by_severity[event.severity] = facts.events_by_severity.get(event.severity, 0) + 1
        facts.events_by_channel[event.channel] = facts.events_by_channel.get(event.channel, 0) + 1
        facts.seconds_by_channel[event.channel] = round(
            facts.seconds_by_channel.get(event.channel, 0.0) + event.duration_s, 1
        )
    facts.positive_moments = sum(1 for e in events if e.type == "smile")

    ranked = {c: s for c, s in channel_scores.items() if s is not None}
    if ranked:
        facts.strongest_channel = max(ranked.items(), key=lambda kv: (kv[1], kv[0]))[0]
        facts.weakest_channel = min(ranked.items(), key=lambda kv: (kv[1], kv[0]))[0]

    return SessionSummary(
        overall_score=overall,
        channel_scores=channel_scores,
        facts=facts,
        summary_text=summary_sentence(overall, channel_scores, events, facts),
    )


CHANNEL_LABEL = {"face": "face and eye contact", "pose": "posture", "hands": "hand movement"}


def summary_sentence(
    overall: float | None,
    channel_scores: dict[str, float | None],
    events: Sequence[Event],
    facts: SessionFacts,
) -> str:
    """A couple of sentences describing the session, built from templates.

    This is the wording the user sees if nothing else produces one. A language model may
    reword it later, but it can only ever rephrase what is written here: the observations
    and their timings are decided before any rewording happens, so nothing can be invented
    at that stage.

    It names one strength and one thing to work on. Only faults would be discouraging and
    people stop reading; only praise would be useless.
    """
    if overall is None:
        return (
            "There was not enough clearly visible footage in this recording to score it. "
            "Check that your face and upper body stay in frame, and try again."
        )

    parts: list[str] = []

    if facts.strongest_channel:
        parts.append(
            f"Your strongest channel this session was {CHANNEL_LABEL.get(facts.strongest_channel, facts.strongest_channel)}."
        )

    sustained = [e for e in events if e.severity in ("low", "medium")]
    if sustained:
        longest = max(sustained, key=lambda e: (e.severity == "medium", e.duration_s))
        parts.append(f"The clearest thing to work on: {longest.message[0].lower()}{longest.message[1:]}")
    else:
        parts.append("Nothing stood out for long enough to be worth flagging, which is a good sign.")

    positive = [e for e in events if e.type == "smile"]
    if positive:
        parts.append(f"There was also a natural smile around {clock(positive[0].t_start_s)}.")

    if facts.windows_skipped > facts.windows_total * 0.25:
        parts.append(
            f"Note that {facts.windows_skipped} of {facts.windows_total} seconds could not be scored, "
            "so this is based on less evidence than usual."
        )

    return " ".join(parts)
