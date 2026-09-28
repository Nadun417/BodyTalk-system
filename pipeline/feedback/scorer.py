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

from .metrics import driving_metric
from .rules import CHANNEL_LABEL, Event, clock

#: The share of the recording a channel score has to rest on before it is treated as a
#: finding about the whole session.
#:
#: A channel's score is the average over the seconds in which that channel could actually be
#: measured, so a channel seen for one second of a seventy-second recording gets a score built
#: from that one second, and on the screen it looks exactly like a score built from all
#: seventy. Below this share the number is kept in the saved results, where the evaluation can
#: still read it, but it is never shown to the user and never named as the strongest or the
#: weakest channel. In its place the screen and the report say how little of the recording the
#: channel could be measured in, which is the part that is actually known. A number with a
#: warning beside it still reads as a number, so the number is left out rather than qualified.
#:
#: Half is the line the channel breakdown already uses for a single measurement, where a
#: measurement available in less than half of its channel's seconds is described as "a rough
#: guide". Using the same line means the two warnings agree about what too little of the
#: session is, instead of each having its own figure.
THIN_CHANNEL_SHARE = 0.5


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
    #: how many seconds each channel's score actually rests on, out of windows_total
    channel_windows: dict[str, int] = field(default_factory=dict)
    #: channels whose score rests on less than THIN_CHANNEL_SHARE of the recording
    thin_channels: list[str] = field(default_factory=list)


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
    metric_reports: dict[str, Sequence] | None = None,
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

    for channel, windows in channel_windows.items():
        facts.channel_windows[channel] = sum(1 for w in windows if w.score is not None)
    facts.thin_channels = [
        channel
        for channel, count in facts.channel_windows.items()
        if channel_scores.get(channel) is not None
        and count < THIN_CHANNEL_SHARE * facts.windows_total
    ]

    # A channel seen for only a sliver of the recording is left out of the comparison. Its
    # score is a few seconds' reading, and calling it the strongest or the weakest channel
    # would present that sliver as a verdict on the whole session.
    ranked = {
        c: s
        for c, s in channel_scores.items()
        if s is not None and c not in facts.thin_channels
    }
    if ranked:
        facts.strongest_channel = max(ranked.items(), key=lambda kv: (kv[1], kv[0]))[0]
        facts.weakest_channel = min(ranked.items(), key=lambda kv: (kv[1], kv[0]))[0]

    return SessionSummary(
        overall_score=overall,
        channel_scores=channel_scores,
        facts=facts,
        summary_text=summary_sentence(
            overall, channel_scores, events, facts, metric_reports
        ),
    )


def summary_sentence(
    overall: float | None,
    channel_scores: dict[str, float | None],
    events: Sequence[Event],
    facts: SessionFacts,
    metric_reports: dict[str, Sequence] | None = None,
) -> str:
    """A couple of sentences describing the session, built from templates.

    This is the wording the user sees if nothing else produces one. A language model may
    reword it later, but it can only ever rephrase what is written here: the observations
    and their timings are decided before any rewording happens, so nothing can be invented
    at that stage.

    It names one strength and one thing to work on. Only faults would be discouraging and
    people stop reading; only praise would be useless.

    It carries no numbers. The scores are on the cards directly above it and the breakdown
    below it, so repeating them here only made the one paragraph everybody reads the hardest
    one to read. The earlier version ran to four numbers in two sentences, of the form "What
    held this back most was level shoulders, which averaged 60 out of 100. For comparison,
    staying upright 75 and sitting still 95."
    """
    if overall is None:
        return (
            "We couldn't see enough of you in this recording to give it a score. "
            "Check your face and upper body are inside the frame, then try again."
        )

    parts: list[str] = []

    if facts.strongest_channel:
        label = CHANNEL_LABEL.get(facts.strongest_channel, facts.strongest_channel)
        parts.append(f"Your {label} came out best this time.")

    sustained = [e for e in events if e.severity in ("low", "medium")]
    if sustained:
        longest = max(sustained, key=lambda e: (e.severity == "medium", e.duration_s))
        parts.append(f"The main thing to work on: {longest.message[0].lower()}{longest.message[1:]}")
    else:
        parts.append("Nothing came up for long enough to flag, which is a good sign.")

    # Naming what held the weakest part back, when one measurement stands out. A score is an
    # average of two or three separate measurements, so a middling one usually means one of
    # them was poor rather than all of them, and somebody reading only the score has no way
    # of telling those apart.
    #
    # Left out when the weakest is also the strongest, which happens when only one part
    # could be ranked at all: calling the same thing best and worst in one paragraph says
    # nothing. And the reason is only named when it rests on at least half of the seconds
    # scored, for the same reason a thin score is not shown at all.
    weakest = facts.weakest_channel
    if metric_reports and weakest and weakest != facts.strongest_channel:
        label = CHANNEL_LABEL.get(weakest, weakest)
        driver = (
            driving_metric(metric_reports.get(weakest) or [])
            if channel_scores.get(weakest) is not None
            else None
        )
        if driver and driver.low_reading and driver.coverage >= 0.5:
            parts.append(
                f"Your {label} scored lowest, and the biggest reason was {driver.low_reading}."
            )

    positive = [e for e in events if e.type == "smile"]
    if positive:
        parts.append(f"You also smiled naturally around {clock(positive[0].t_start_s)}.")

    # Said in words because the score itself is not shown for such a part, and a score
    # missing without explanation looks like a fault in the app. It says how little was
    # measured and nothing about why: it may have been out of shot, hidden or simply not
    # picked up, and the data cannot tell those apart.
    for channel in facts.thin_channels:
        label = CHANNEL_LABEL.get(channel, channel)
        parts.append(
            f"We could only measure your {label} for {facts.channel_windows.get(channel, 0)} "
            f"of the {facts.windows_total} seconds, which is too little to score."
        )

    if facts.windows_skipped > facts.windows_total * 0.25:
        parts.append(
            f"We couldn't measure {facts.windows_skipped} of the {facts.windows_total} seconds, "
            "so this is based on less of the recording than usual."
        )

    return " ".join(parts)
