"""Spotting stretches worth commenting on, and wording them for the user.

These are written as ordinary functions and should stay that way. All they do is check
numbers against thresholds and look at how long something went on for, which reads
perfectly clearly written out plainly. Wrapping that up in layers of handler classes or a
configurable rules engine would make it harder to follow, not easier, and there is
nothing here that needs the flexibility.

Two rules matter for how this behaves:

Nothing fires on a single moment. A behaviour has to keep up for a while before it counts,
otherwise every small shift produces a comment and the feedback becomes noise the user
learns to ignore. Someone glancing away once is not a habit worth flagging.

The wording stays with what was visible. "Your hands were out of shot from 0:30 to 0:45"
is something the user can check against their own recording and decide what to do about.
"You seemed nervous" is not, because nothing here can tell the difference between nerves,
concentration and a person who simply keeps still when thinking. Where a comment rests on
a stretch of video that was poorly seen, it gets marked as less certain rather than
stated flatly.
"""

from __future__ import annotations


def derive_events(window_scores: list[dict]) -> list[dict]:
    """Return the timestamped comments as a list of dictionaries, each holding
    {tStartS, tEndS, channel, type, severity, message, suggestion}.

    Written during the feedback stage of implementation.
    """
    raise NotImplementedError("Feedback rules are implemented during the Feedback Engine task.")
