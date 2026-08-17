"""The shared interface for the three channel analysers, plus the helpers they all use.

Face, pose and hands each measure completely different things, but they all answer the
same two questions about a slice of video: how did this channel score, and how clearly
could it be seen? Because they all answer in the same shape, the fusion stage can work
through a list of analysers without knowing or caring which is which.

The rest of this module is the small toolkit all three share. These live here rather than
being repeated in each analyser so that there is only one copy to change, and so the three
channels cannot quietly drift into measuring things slightly differently:

  scale()          turns a raw measurement into a 0 to 100 score
  Window           one second of frames, plus window_frames() to build them
  dist(), spread() distance and scatter, corrected for the shape of the frame
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from typing import Iterable, Iterator, NamedTuple, Sequence, TypedDict

#: How long one analysis window is, in seconds. Scores, fusion, the database rows
#: and the dashboard charts are all built on this same unit.
WINDOW_S = 1.0


class AnalysisResult(TypedDict):
    """What one analyser hands back for one window."""

    score: float | None  # 0 to 100, or None if the channel could not be seen at all
    visibility: float  # 0 to 1, how well this channel could be seen in this window


def scale(x: float, x_bad: float, x_good: float) -> float:
    """Turn a raw measurement into a score from 0 to 100.

    Give it the measurement, the value that deserves 0, and the value that deserves 100.
    Anything in between is placed proportionally along a straight line, and anything
    beyond either end is pulled back to 0 or 100 so scores never leave the range.

    It does not matter which of the two reference values is the larger number, so the
    same function handles both directions without any special cases:

        smaller is better   scale(sway, 0.06, 0.008)
        larger is better    scale(liveliness, 0.002, 0.020)
    """
    if x_bad == x_good:  # no range to work with, so fall back to pass or fail
        return 100.0 if x >= x_good else 0.0
    t = (x - x_bad) / (x_good - x_bad)
    return max(0.0, min(100.0, 100.0 * t))


# ------------------------------------------------------------------------------ geometry
#
# MediaPipe does not report landmark positions in pixels. It reports them as fractions of
# the frame: x as a fraction of the frame's WIDTH, y as a fraction of its HEIGHT. On a
# frame that is not square those two fractions stand for different real distances, so
# measuring straight across normalised coordinates comes out stretched sideways. On a
# 16:9 clip something physically square measures about 1.78 times wider than it is tall.
#
# This matters because several metrics divide a measurement taken in one direction by a
# reference taken in the other. Mouth openness is vertical and gets divided by face width,
# which is horizontal. Without a correction the same person gives a different number on a
# widescreen clip than on a squarer one, and a threshold tuned on one shape of video is
# simply wrong on the other.
#
# The fix is to multiply x by the aspect ratio (width divided by height) to get back to
# even units before measuring anything. Every distance below goes through that step.


def square(point: Sequence[float], aspect: float) -> tuple[float, float]:
    """Convert a normalised (x, y) into even units by stretching x back out."""
    return (point[0] * aspect, point[1])


def dist(a: Sequence[float], b: Sequence[float], aspect: float) -> float:
    """Straight-line distance between two landmarks, in aspect-corrected units."""
    ax, ay = square(a, aspect)
    bx, by = square(b, aspect)
    return math.hypot(ax - bx, ay - by)


def spread(points: Iterable[Sequence[float]], aspect: float) -> float:
    """How scattered a set of positions is, in aspect-corrected units.

    The stability metrics use this. They take one landmark, such as the tip of the nose,
    collect where it was in every frame of the window, and ask how much it wandered. A
    steady head gives a small number, a head that kept moving gives a large one.

    Scatter in two dimensions is measured here as the square root of the horizontal
    variance plus the vertical variance, which is the average distance of the points from
    their own centre. The design describes this only as the standard deviation of a point
    without saying how the two directions should be combined, so this is that decision
    written down.
    """
    pts = [square(p, aspect) for p in points]
    n = len(pts)
    if n < 2:
        return 0.0
    mean_x = sum(p[0] for p in pts) / n
    mean_y = sum(p[1] for p in pts) / n
    var_x = sum((p[0] - mean_x) ** 2 for p in pts) / n
    var_y = sum((p[1] - mean_y) ** 2 for p in pts) / n
    return math.sqrt(var_x + var_y)


# ----------------------------------------------------------------------------- windowing


class Window(NamedTuple):
    """One second of sampled frames, which is the unit everything downstream works in.

    At the default rate of six frames a second, a window holds roughly six frames. That
    is long enough that one bad frame gets averaged away, and short enough that when the
    dashboard says a behaviour happened at 1:23 it is close enough to be useful.
    """

    index: int  # 0, 1, 2 and so on from the start of the video
    t_start_s: float
    t_end_s: float
    frames: list[dict]  # the frame records that fell inside this window


def window_frames(frames: Iterable[dict], window_s: float = WINDOW_S) -> Iterator[Window]:
    """Group frame records into back-to-back windows of fixed length.

    Frames are expected in time order, which is how they are written to the cache file.

    A window with no frames in it is skipped rather than handed on empty. At six frames a
    second that only happens if the source video itself had a gap, and passing an empty
    window downstream would only give the analysers nothing to work with.
    """
    current: list[dict] = []
    current_index: int | None = None

    for frame in frames:
        index = int(frame["tS"] // window_s)
        if current_index is None:
            current_index = index
        elif index != current_index:
            yield Window(
                index=current_index,
                t_start_s=current_index * window_s,
                t_end_s=(current_index + 1) * window_s,
                frames=current,
            )
            current = []
            current_index = index
        current.append(frame)

    # The loop above only emits a window when the next one starts, so the final
    # window is still sitting in `current` when the frames run out.
    if current and current_index is not None:
        yield Window(
            index=current_index,
            t_start_s=current_index * window_s,
            t_end_s=(current_index + 1) * window_s,
            frames=current,
        )


def presence_rate(window: Window, *keys: str) -> float:
    """What fraction of the window's frames had the given channel detected.

    This stands in for visibility on the face and hand channels. MediaPipe gives a proper
    per-landmark visibility number for body pose, but not for the face mesh or the hands,
    so for those two the next best thing is how often the channel was found at all.

    Pass one key for the face. Pass both hand keys together and the result works out as
    the average of nothing detected, one hand detected and two hands detected, which is
    the 0, 0.5 or 1.0 per frame that the hands channel needs.
    """
    if not window.frames:
        return 0.0
    total = 0.0
    for frame in window.frames:
        found = sum(1 for key in keys if frame[key]["detected"])
        total += found / len(keys)
    return total / len(window.frames)


class Analyser(ABC):
    """One behavioural channel. Windows are fed in one at a time, in time order.

    An analyser is allowed to remember things between windows. The face analyser does
    exactly that, keeping the last ten seconds of measurements so it can judge whether an
    expression is animated. Because of that, one instance handles one video from start to
    finish, and the windows have to arrive in order.
    """

    #: which channel this is: "face", "pose" or "hands"
    channel: str

    @abstractmethod
    def analyse(self, window: Window) -> AnalysisResult:
        """Reduce one window down to a score and this channel's visibility."""
