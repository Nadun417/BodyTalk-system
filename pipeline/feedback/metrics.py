"""Working out which measurement actually caused a channel score, and saying so plainly.

A channel score is an average, and an average hides its own workings. "Your face scored 66"
could mean three mediocre measurements or, as it usually turns out to mean in practice, two
that were close to perfect and a third sitting on the floor. Those two situations call for
completely different advice, and the score alone cannot tell them apart. Neither can the
user, which is the real problem: being told to work on your face and eye contact when your
eye contact was fine throughout is advice that is both useless and slightly insulting.

So this file takes the score back apart. For each channel it reports every measurement that
went into it, how that measurement averaged, how much of the video it could be measured in,
and, most usefully, exactly how many points of the channel's shortfall it is responsible for.

**The split is exact, not an estimate.** That is worth explaining, because it is the reason
these numbers can be quoted to the user as fact. A channel's score in one window is the mean
of the measurements available in that window, so the amount that window fell short of 100 is
the mean of the amounts each measurement fell short by. Splitting that shortfall between the
measurements is therefore just arithmetic, and adding the pieces back up returns the original
score with nothing left over. A test asserts exactly that.

The one subtlety is that not every measurement is available in every window. A window where
the hands were not visible has no gesture reading, and it would be wrong to charge gesture
for a shortfall it had no part in. So each window is divided only between the measurements
actually present in it, which is also precisely how the score itself was worked out.

Nothing here judges anybody. It reports which measurement pulled a number down, in the same
observational terms as everything else: a low expression-variation reading means the face
moved little, not that the person felt little.
"""

from __future__ import annotations

import statistics as stats
from dataclasses import dataclass
from typing import Sequence

from analysers import CHANNEL_METRICS, MetricSpec

#: Below this, a measurement is not worth naming as the cause of anything. A measurement
#: that pulled a channel down by less than a point out of a hundred did not meaningfully
#: shape the score, and pointing at it would be reading noise aloud. This governs only
#: whether a sentence gets written, never any score.
NEGLIGIBLE_SHORTFALL = 1.0


@dataclass
class MetricReport:
    """How one measurement behaved across a whole session, and what it cost the channel."""

    channel: str
    metric: str
    #: how this measurement is described to the user, in plain words
    label: str
    #: whether it counted toward the channel score at all. A measurement that did not count
    #: is reported for interest and must never be given as the reason for a score.
    scored: bool
    #: its average across the windows it could be measured in, 0 to 100, or None if it
    #: could never be measured
    mean_score: float | None
    #: how many windows it could be measured in
    windows: int
    #: that as a fraction of the windows the channel was scored in, so a measurement based
    #: on very little of the video can be recognised as such rather than quoted flatly
    coverage: float
    #: how many points, out of 100, this measurement pulled the channel score down by.
    #: Always 0 for a measurement that does not count toward the score.
    shortfall: float

    @property
    def negligible(self) -> bool:
        return self.shortfall < NEGLIGIBLE_SHORTFALL


def metric_reports(channel_windows: dict[str, Sequence]) -> dict[str, list[MetricReport]]:
    """Break every channel's score down into the measurements that produced it.

    Returns one list per channel, worst offender first, so the head of each list is the
    thing most worth telling the user about.

    Only windows where the channel actually produced a score are considered. Windows where
    nothing could be seen are missing evidence rather than poor performance, and the score
    itself already excludes them, so including them here would attribute a shortfall that
    was never in the score to begin with.
    """
    out: dict[str, list[MetricReport]] = {}

    for channel, windows in channel_windows.items():
        specs = CHANNEL_METRICS.get(channel, ())
        scored_windows = [w for w in windows if w.score is not None]
        out[channel] = [
            _report_for(channel, spec, windows, scored_windows, specs) for spec in specs
        ]
        out[channel].sort(key=lambda r: (-r.shortfall, r.metric))

    return out


def _report_for(
    channel: str,
    spec: MetricSpec,
    all_windows: Sequence,
    scored_windows: Sequence,
    specs: Sequence[MetricSpec],
) -> MetricReport:
    """Summarise one measurement across the session.

    The average is taken over every window the measurement exists in, including windows
    where the channel as a whole went unscored, because the average is a description of the
    measurement itself. The shortfall is taken only over windows that were scored, because
    that is a description of the score, and the score never saw the others.
    """
    present = [
        getattr(w, spec.attribute) for w in all_windows if getattr(w, spec.attribute, None) is not None
    ]
    mean_score = stats.fmean(present) if present else None

    counting = [s.attribute for s in specs if s.scored]
    shortfall = 0.0
    covered = 0

    if spec.scored and scored_windows:
        total = 0.0
        for window in scored_windows:
            # How many measurements shared this window's score, which is what each of them
            # was divided by when the score was worked out.
            share_count = sum(
                1 for attribute in counting if getattr(window, attribute, None) is not None
            )
            value = getattr(window, spec.attribute, None)
            if value is None or share_count == 0:
                continue
            covered += 1
            total += (100.0 - value) / share_count
        shortfall = total / len(scored_windows)
    elif scored_windows:
        covered = sum(
            1 for w in scored_windows if getattr(w, spec.attribute, None) is not None
        )

    return MetricReport(
        channel=channel,
        metric=spec.attribute,
        label=spec.label,
        scored=spec.scored,
        mean_score=mean_score,
        windows=len(present),
        coverage=covered / len(scored_windows) if scored_windows else 0.0,
        shortfall=shortfall,
    )


def driving_metric(reports: Sequence[MetricReport]) -> MetricReport | None:
    """The measurement most responsible for a channel falling short, if any is.

    Returns nothing when the channel scored well enough that no measurement meaningfully
    held it back. Naming one anyway would manufacture a fault out of a good result, which
    is exactly the sort of thing that teaches people to stop trusting the feedback.
    """
    candidates = [r for r in reports if r.scored and not r.negligible]
    return candidates[0] if candidates else None


def explain_channel(
    channel_score: float | None,
    reports: Sequence[MetricReport],
) -> str | None:
    """One plain sentence saying which measurement held a channel back, and by how much.

    Written as numbers rather than as adjectives on purpose. "Expression variation averaged
    1 out of 100" is checkable and tells somebody what to change; "your expression was
    somewhat lacking" is neither. It also avoids having to invent cut-offs for words like
    "poor" or "excellent", which would be three more unevidenced thresholds in a project
    that already has enough of them.

    Returns nothing when there is nothing worth explaining, either because the channel was
    never scored or because no single measurement held it back.
    """
    if channel_score is None:
        return None
    driver = driving_metric(reports)
    if driver is None or driver.mean_score is None:
        return None

    # "What held this back most" rather than "most of the gap came from", because the
    # first is true by construction and the second is not. The driving measurement is the
    # largest single contributor, which does not have to mean it is more than half of it.
    sentence = (
        f"What held this back most was {driver.label}, which averaged "
        f"{driver.mean_score:.0f} out of 100."
    )

    # Naming what went well alongside it is not decoration. Without it the sentence reads
    # as though the whole channel was weak, which is the misreading this exists to correct.
    others = [
        r
        for r in reports
        if r.scored and r.metric != driver.metric and r.mean_score is not None
    ]
    if others:
        sentence += (
            f" For comparison, {_join([f'{r.label} {r.mean_score:.0f}' for r in others])}."
        )

    if driver.coverage < 0.5:
        sentence += (
            f" It could only be measured in {driver.coverage * 100:.0f} percent of the "
            "session, so treat it as a hint rather than a finding."
        )

    return sentence


def _join(labels: Sequence[str]) -> str:
    """Join labels the way a person writes a list: a, b and c."""
    if len(labels) == 1:
        return labels[0]
    return f"{', '.join(labels[:-1])} and {labels[-1]}"
