"""Saving the detected landmarks for every frame, one JSON object per line.

Why bother saving them at all. Detection is by far the slowest part of the pipeline, taking
minutes to get through a single clip. Doing that once and keeping the output means the
analysers, the fusion stage and the feedback rules can all be developed against a file that
loads in a moment, rather than sitting through detection again after every small code
change. It turns a wait of minutes into no wait at all.

The format. One JSON object per line. The first line describes how the file was made, and
every line after it is one analysed frame. Reading it back is an ordinary loop over the
lines, so nothing has to hold the whole file in memory at once. That matters more than it
sounds: a four minute clip comes to roughly 20 MB of landmark data.

The version number on these files stays where it is. Raising it would mark every cache
already sitting on disk as out of date, and regenerating them is exactly the slow job this
whole file exists to avoid.

A note on the folder name: this would more naturally be called `io`, but a package with
that name sitting at the top level gets picked up instead of Python's own `io` module once
the pipeline folder is on the import path, which breaks things in confusing ways.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator

#: Raise this only if the shape of a frame record changes. It has nothing to do with the
#: format of results.json, which is versioned separately.
SCHEMA_VERSION = 1


def make_header(
    video: str,
    video_duration_s: float,
    source_fps: float,
    analysis_fps: float,
    frame_width: int,
    frame_height: int,
    mediapipe_version: str,
    refine_face_landmarks: bool = False,
) -> dict:
    """Build the first line of a cache file, which describes the file itself.

    Recording the model version and the sampling rate is what makes it possible to pick one
    of these files up months later and know exactly how it was produced. Without that, a
    cache file is just numbers with no way of telling whether they are still trustworthy.

    The frame dimensions are stored for a specific reason rather than for completeness.
    MediaPipe measures x as a fraction of the frame's width and y as a fraction of its
    height, so on a frame that is not square those two fractions mean different real
    distances. Any measurement that divides a vertical distance by a horizontal one needs
    the ratio between width and height to undo that. Leave the dimensions out and the file
    cannot be interpreted on its own, which would defeat the point of saving it.
    """
    return {
        "type": "header",
        "schemaVersion": SCHEMA_VERSION,
        "video": video,
        "videoDurationS": round(video_duration_s, 3),
        "sourceFps": round(source_fps, 3),
        "analysisFps": round(analysis_fps, 3),
        "frame": {"width": frame_width, "height": frame_height},
        "mediapipe": {
            "version": mediapipe_version,
            "refineFaceLandmarks": refine_face_landmarks,
        },
        "createdAt": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
    }


def aspect_of(header: dict) -> float:
    """Frame width divided by height, used to even out the coordinates before measuring.

    Older cache files were written before the frame dimensions were recorded. Rather than
    refusing to read them, this returns 1.0 for those, which means no correction is applied
    and they behave the way they did when they were made.
    """
    frame = header.get("frame") or {}
    width, height = frame.get("width"), frame.get("height")
    if not width or not height:
        return 1.0
    return width / height


def make_frame(frame_index: int, t_s: float, channels: dict) -> dict:
    """Package one detector result into a frame record.

    `channels` is whatever the detector handed back: the face, pose, left hand and right
    hand slots. A frame where nothing at all was found still gets written out, with every
    slot marked as not detected. Keeping one line per sampled frame means later code can
    count on the file lining up with the video, instead of having to work out which frames
    are missing and why.
    """
    return {
        "type": "frame",
        "frameIndex": frame_index,
        "tS": round(t_s, 3),
        **channels,
    }


def write_landmarks(
    path: str | Path,
    frames: Iterable[dict],
    header: dict | None = None,
) -> int:
    """Write the header and then every frame to `path`, returning how many frames went in.

    The frames are pulled through one at a time rather than gathered up first, so this can
    be handed a generator that is still busy running detection. Nothing piles up in memory
    while a long clip is being processed.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    count = 0
    with path.open("w", encoding="utf-8") as fh:
        if header is not None:
            fh.write(json.dumps(header, separators=(",", ":")) + "\n")
        for frame in frames:
            fh.write(json.dumps(frame, separators=(",", ":")) + "\n")
            count += 1
    return count


def read_landmarks(path: str | Path) -> Iterator[dict]:
    """Go through the file and hand back every record in it, header included."""
    with Path(path).open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def read_header(path: str | Path) -> dict:
    """Return just the header record from the front of the file.

    Complains rather than guessing if the first line is not a header. That usually means
    the file was cut short partway through writing, or was produced by an older version of
    this code, and either way carrying on would give quietly wrong measurements.
    """
    for record in read_landmarks(path):
        if record.get("type") == "header":
            return record
        raise ValueError(f"{path} does not start with a header line")
    raise ValueError(f"{path} is empty")


def read_frames(path: str | Path) -> Iterator[dict]:
    """Hand back only the frame records, skipping past the header.

    This is the one the analysers use.
    """
    for record in read_landmarks(path):
        if record.get("type") == "frame":
            yield record
