"""Writes results.json, which holds the finished scores and comments for one run.

This file is where the Python side stops. It writes the results into the session folder
and does nothing further; the desktop application picks the file up from there and is the
only part that ever writes to the database.

Splitting it that way keeps all the database code in one language instead of having two
different programs writing to the same tables and having to agree about it. The field
names and units here have to match what the application expects to read, so changing one
side means changing the other.
"""

from __future__ import annotations

import json


def write_results(path: str, result: dict) -> None:
    """Save the run result as results.json.

    Written out indented rather than as one long line, because during development this
    file gets opened and read by hand constantly.
    """
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2)
