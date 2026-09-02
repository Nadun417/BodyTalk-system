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

#: Bumped whenever the shape below changes. Kept separate from the landmark cache version,
#: which moves independently.
SCHEMA_VERSION = 2

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
            }
        )

    return {
        "schemaVersion": SCHEMA_VERSION,
        "fusionMode": fusion_mode,
        "overallScore": _round(summary.overall_score, 1),
        "channelScores": {
            channel: _round(score, 1) for channel, score in summary.channel_scores.items()
        },
        "overallSummary": summary.summary_text,
        "summaryPhrasing": "template",
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
                "phrasing": "template",
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
                "phrasing": "template",
            }
            for rec in recommendations
        ],
        "meta": {
            "analysisFps": round(analysis_fps, 2),
            "windowS": window_s,
            "fusionParams": fusion_params,
            "mediapipe": {"version": mediapipe_version},
            "llm": {"model": None, "used": False},
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
