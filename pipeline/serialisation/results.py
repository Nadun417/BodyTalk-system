"""Writes results.json, which holds the finished scores and comments for one run.

This file is where the Python side stops. It writes the results into the session folder and
does nothing further; the desktop application picks the file up from there and is the only
part that ever writes to the database.

Splitting it that way keeps all the database code in one language instead of having two
different programs writing to the same tables and having to agree about it. The field names
and units here have to match what the application expects to read, so changing one side
means changing the other.

Two fields say how the wording was produced: `summaryPhrasing` on the session and
`phrasing` on every observation. Both currently read `template`, because the wording comes
from fixed sentences assembled here. If a language model is added later to reword them,
these are what record which path each piece of text took, so a result can always be traced
back to whether a machine phrased it or a template did.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

from analysers import CHANNEL_METRICS

#: Bumped whenever the shape below changes. Kept separate from the landmark cache version,
#: which moves independently.
#:
#: Version 3 added the individual measurements behind each channel score, both per window
#: and summarised across the session. Before that only the channel score was kept, so
#: nothing downstream could say whether a face score of 66 meant three middling
#: measurements or two good ones and a third on the floor.
#:
#: Version 4 added how much of the recording each channel score rests on. A channel seen for
#: one second gets a score from that one second, and without this nothing downstream could
#: tell it apart from a score built from the whole recording.
SCHEMA_VERSION = 4

CHANNELS = ("face", "pose", "hands")


def _round(value: float | None, places: int = 2) -> float | None:
    return None if value is None else round(value, places)


def build_result(
    fusion_mode: str,
    fused: Sequence,
    channel_windows: dict[str, Sequence],
    summary,
    events: Sequence,
    recommendations: Sequence,
    analysis_fps: float,
    window_s: float,
    fusion_params: dict,
    mediapipe_version: str,
    phrasing: dict | None = None,
    metric_reports: dict[str, Sequence] | None = None,
) -> dict:
    """Assemble the finished analysis into the shape the application reads.

    `fused` is one entry per window holding the combined score and the weights that
    produced it, in the same order as the per-channel windows.

    Every window contributes four rows: one for each channel and one for the combined
    result. That is more verbose than nesting them, but it is the shape the database table
    and the charts both want, and flattening it here means neither of them has to.
    """
    windows: list[dict] = []
    for index, combined in enumerate(fused):
        row_start = row_end = None
        for channel in CHANNELS:
            series = channel_windows.get(channel) or []
            if index >= len(series):
                continue
            window = series[index]
            row_start, row_end = window.t_start_s, window.t_end_s
            weight = combined.weights.get(channel) if combined is not None else None
            windows.append(
                {
                    "tStartS": window.t_start_s,
                    "tEndS": window.t_end_s,
                    "channel": channel,
                    "rawScore": _round(window.score, 1),
                    "visibility": _round(window.visibility, 3),
                    "weight": _round(weight, 3),
                    # The measurements the channel score was averaged from. Kept because
                    # the score alone cannot say which of them caused it, and because
                    # choosing better cut-offs later needs the measurement sitting next to
                    # the score it produced rather than a guess about what it might be.
                    "metrics": {
                        spec.attribute: _round(getattr(window, spec.attribute, None), 1)
                        for spec in CHANNEL_METRICS.get(channel, ())
                    },
                }
            )
        if row_start is None:
            continue
        # The combined row carries no visibility or weight of its own: it is the product of
        # the three above it, not a fourth thing that was measured.
        windows.append(
            {
                "tStartS": row_start,
                "tEndS": row_end,
                "channel": "fused",
                "rawScore": _round(combined.score if combined is not None else None, 1),
                "visibility": None,
                "weight": None,
                # The combined row measures nothing of its own, so it has no measurements
                # to list. An empty object rather than a missing field, so that every row
                # in this list has the same shape.
                "metrics": {},
            }
        )

    return {
        "schemaVersion": SCHEMA_VERSION,
        "fusionMode": fusion_mode,
        "overallScore": _round(summary.overall_score, 1),
        "channelScores": {
            channel: _round(score, 1) for channel, score in summary.channel_scores.items()
        },
        # How many of the recording's seconds each channel score rests on, and whether that is
        # too few to present the score as a finding about the whole session. The judgement is
        # made here, once, so the screen and the report cannot disagree about it.
        "channelCoverage": {
            channel: {
                "windows": summary.facts.channel_windows.get(channel, 0),
                "of": summary.facts.windows_total,
                "thin": channel in summary.facts.thin_channels,
            }
            for channel in summary.channel_scores
        },
        "overallSummary": summary.summary_text,
        "summaryPhrasing": "template",
        # How each channel score was arrived at, worst offender first. `shortfall` is how
        # many points out of 100 that measurement pulled its channel down by, and the
        # shortfalls within a channel add up exactly to the gap between its score and 100.
        "channelMetrics": [
            {
                "channel": report.channel,
                "metric": report.metric,
                "label": report.label,
                "scored": report.scored,
                "meanScore": _round(report.mean_score, 1),
                "windows": report.windows,
                "coverage": _round(report.coverage, 3),
                "shortfall": _round(report.shortfall, 2),
            }
            for channel in CHANNELS
            for report in (metric_reports or {}).get(channel, ())
        ],
        "windows": windows,
        "events": [
            {
                "tStartS": round(event.t_start_s, 2),
                "tEndS": round(event.t_end_s, 2),
                "channel": event.channel,
                "type": event.type,
                "severity": event.severity,
                "message": event.message,
                "suggestion": event.suggestion,
                "phrasing": event.phrasing,
            }
            for event in events
        ],
        "recommendations": [
            {
                "rank": rec.rank,
                "channel": rec.channel,
                "kind": rec.kind,
                "title": rec.title,
                "body": rec.body,
                "basisEventTypes": rec.basis_event_types,
                "phrasing": rec.phrasing,
                # Never reworded by anything, unlike the body above it: this one carries
                # numbers, and numbers are not the phrasing step's to touch.
                "detail": rec.detail,
            }
            for rec in recommendations
        ],
        "meta": {
            "analysisFps": round(analysis_fps, 2),
            "windowS": window_s,
            "fusionParams": fusion_params,
            "mediapipe": {"version": mediapipe_version},
            # What, if anything, a language model contributed, and how often its wording had
            # to be refused. The refusal count is the honest half of this: it is the
            # difference between saying a model was used and showing how it was governed.
            "llm": phrasing or {"used": False, "reworded": 0, "refused": 0, "why": "not switched on"},
            "windowsScored": summary.facts.windows_scored,
            "windowsSkipped": summary.facts.windows_skipped,
        },
    }


def write_results(path: str | Path, result: dict) -> None:
    """Save the run result as results.json.

    Written out indented rather than as one long line, because during development this file
    gets opened and read by hand constantly.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2)


def read_results(path: str | Path) -> dict:
    """Load a saved result back, for tests and for comparing two runs of the same video."""
    with Path(path).open("r", encoding="utf-8") as fh:
        return json.load(fh)
