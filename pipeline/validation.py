"""Checking whether an uploaded video is worth analysing, before spending minutes on it.

Analysing a three minute clip takes a few minutes of real time. The worst possible outcome
is for someone to wait all of that out and then be told the file was never going to work.
So the checks happen first, they happen in a few seconds, and they say in plain words what
was wrong.

Four things are checked, cheapest first:

  1. the file exists and is not so large that copying it would be a problem
  2. it can actually be opened and decoded as a video
  3. its length is inside the range that can usefully be analysed
  4. somebody is actually visible in it

The order matters, and it is ordered by cost rather than by importance. Looking up a file's
size costs nothing, opening it is nearly free, reading its length costs almost nothing more,
and only the last check has to run the detector at all. There is no point asking whether a
person is visible in a file that will not even open.

**On checking the format.** There is deliberately no list of accepted file types here. A
list of extensions would be a lie in both directions: a file named `.mp4` can hold video
encoded in a way this computer cannot decode, and a perfectly readable file can arrive with
the wrong name on it. The honest test is to open the file and decode a frame from it. If
that works, it works, and if it does not, the error message can say so plainly instead of
arguing about the name.

**On counting people.** The requirements ask this stage to confirm a *single* detectable
person. That cannot be done with the detector this project uses. It is built to follow
exactly one person and returns at most one set of body landmarks, so if two people are in
shot it quietly picks one and carries on. It can never report that it saw two. What is
checked here is therefore that *somebody* is visible, and the single-subject requirement is
handled by telling the user about it rather than by enforcing it. This was settled during
design rather than discovered here, and it is written down as a known limitation.

Nothing in this file writes anything. It reads the video, forms a judgement and hands it
back, which keeps it easy to test and means a rejected file leaves no trace behind.
"""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

#: How short a clip is allowed to be, and how much of that the user is allowed to change.
#: The default is sixty seconds. The feedback rules look for behaviour that carries on for
#: several seconds at a time, so a very short clip produces a score with almost nothing
#: behind it. Thirty seconds is the point below which that stops being worth reporting at
#: all, and a hundred and eighty is as high as the bar can sensibly be set before ordinary
#: practice answers start being turned away.
DEFAULT_MIN_DURATION_S = 60.0
MIN_DURATION_FLOOR_S = 30.0
MIN_DURATION_CEILING_S = 180.0

#: The upper limits, which exist for different reasons from the lower one.
#:
#: Ten minutes is roughly three times the length the performance budget was written around,
#: which leaves headroom without letting somebody sit through a forty minute analysis. Two
#: gigabytes is comfortably past a ten minute recording from a phone, and the limit matters
#: because the video is copied into the session folder, so a careless upload would otherwise
#: fill a student laptop's disk.
MAX_DURATION_S = 600.0
MAX_FILE_BYTES = 2 * 1024 * 1024 * 1024

#: Below this, on the shorter side of the frame, the picture is warned about rather than
#: refused. Small frames do make the landmarks less reliable, but pixel count is a poor way
#: to judge that when the check is about to look at the actual footage and find out. If a
#: person is clearly visible in a small frame, refusing it would be arguing with the
#: evidence.
#:
#: Warning rather than refusing is a settled decision. The number itself is not: 480 is an
#: untested starting figure, like every other threshold in the project. Moving it changes
#: only how often the note appears, never whether a video is accepted.
LOW_RESOLUTION_SHORT_SIDE_PX = 480

#: How many frames to look at when checking somebody is there, and how many of those have
#: to contain a person. Eight frames spread across the whole clip is enough to tell an empty
#: room from an occupied one while taking about a second to do it. Requiring only half of
#: them to succeed leaves room for the subject briefly leaving the shot, or for a frame or
#: two where the detector simply fails, without rejecting a video that is basically fine.
#:
#: Taking the frames from across the whole clip, rather than from the opening seconds, is a
#: deliberate departure from the original plan. Somebody who sits down and settles a few
#: seconds after pressing record would fail a check that only looked at the beginning, and
#: that is a very ordinary way to record yourself.
PERSON_CHECK_FRAMES = 8
PERSON_CHECK_MIN_RATE = 0.5


class VideoFacts(NamedTuple):
    """What was actually observed about the file, separately from what it means.

    Keeping the observations apart from the verdict is what makes this testable. The
    judgement can then be checked against made-up facts without needing a video, a camera
    or the detector, which is the difference between a test suite that runs anywhere and one
    that only runs on a machine with everything installed.
    """

    exists: bool
    opened: bool
    file_bytes: int = 0
    #: Zero when the file did not say how long it is. Some files genuinely do not report a
    #: frame count, and a made-up length would be worse than admitting it is unknown.
    duration_s: float = 0.0
    width: int = 0
    height: int = 0
    source_fps: float = 0.0
    total_frames: int = 0
    #: False when the detector was not available, which is different from finding nobody.
    person_check_ran: bool = False
    frames_checked: int = 0
    frames_with_person: int = 0


class Validation(NamedTuple):
    """The verdict, and everything the caller needs to explain it to the user."""

    ok: bool
    #: A short tag for the calling code to branch on, so it never has to match on wording.
    code: str
    #: The sentence shown to the user. Empty when the file was accepted.
    reason: str = ""
    duration_s: float = 0.0
    width: int = 0
    height: int = 0
    source_fps: float = 0.0
    #: Things worth mentioning that are not grounds for refusing the file.
    warnings: tuple[str, ...] = ()


def clamp_minimum(min_duration_s: float) -> float:
    """Keep the configured minimum length inside the range the design allows.

    The setting is under the user's control, and a setting under the user's control will
    eventually hold something silly. Clamping here rather than trusting the caller means the
    limit is enforced in the one place that actually applies it.
    """
    if min_duration_s <= 0:
        return DEFAULT_MIN_DURATION_S
    return max(MIN_DURATION_FLOOR_S, min(MIN_DURATION_CEILING_S, float(min_duration_s)))


def judge(facts: VideoFacts, min_duration_s: float = DEFAULT_MIN_DURATION_S) -> Validation:
    """Turn what was observed about a file into an accept or reject, with a reason.

    Pure decision making: it reads no files and calls no detector. Every message it produces
    is written to be read by somebody who has just been stopped from doing the thing they
    wanted to do, so each one says what was wrong and what would fix it.
    """
    minimum = clamp_minimum(min_duration_s)
    warnings: list[str] = []

    if not facts.exists:
        return Validation(
            ok=False,
            code="not_found",
            reason="That file could not be found. It may have been moved or renamed.",
        )

    if facts.file_bytes > MAX_FILE_BYTES:
        # Checked before opening the file, because it is the one thing that can be known
        # without reading a single byte of the video itself.
        gigabytes = MAX_FILE_BYTES / (1024 * 1024 * 1024)
        return Validation(
            ok=False,
            code="too_large",
            reason=(
                f"This file is over {gigabytes:.0f} GB, which is larger than can be handled. "
                "Exporting the recording at a lower resolution will usually bring it well "
                "under."
            ),
        )

    if not facts.opened:
        return Validation(
            ok=False,
            code="unreadable",
            reason=(
                "That file could not be opened as a video. It may be damaged, or saved in a "
                "format this computer cannot play. Recordings saved as MP4 or WebM are the "
                "safest choice."
            ),
        )

    measurements = {
        "duration_s": round(facts.duration_s, 1),
        "width": facts.width,
        "height": facts.height,
        "source_fps": round(facts.source_fps, 2),
    }

    if facts.duration_s <= 0:
        # The file opened and gave us frames but never said how long it is. Analysing it is
        # still perfectly possible, so refusing it would be punishing the user for something
        # in the file's own bookkeeping. Say so and carry on.
        warnings.append(
            "The length of this video could not be read, so it was not checked against the "
            "minimum. The analysis will still run."
        )
    elif facts.duration_s < minimum:
        seconds = int(round(facts.duration_s))
        return Validation(
            ok=False,
            code="too_short",
            reason=(
                f"That clip is about {seconds} seconds long, and at least "
                f"{int(round(minimum))} seconds are needed. The feedback looks for habits "
                "that carry on for several seconds, so a shorter clip has too little in it "
                "to say anything useful about."
            ),
            warnings=tuple(warnings),
            **measurements,
        )

    elif facts.duration_s > MAX_DURATION_S:
        return Validation(
            ok=False,
            code="too_long",
            reason=(
                f"Videos longer than {int(MAX_DURATION_S // 60)} minutes are not supported. "
                "Trimming the recording down to your best answer will analyse faster and "
                "give more focused feedback anyway."
            ),
            warnings=tuple(warnings),
            **measurements,
        )

    short_side = min(facts.width, facts.height)
    if 0 < short_side < LOW_RESOLUTION_SHORT_SIDE_PX:
        # A warning rather than a refusal, and deliberately so. The check is about to look at
        # the footage and find out whether the person can actually be seen, which is far
        # better evidence than counting pixels. Refusing a small video in which somebody is
        # plainly visible would be arguing with what the detector has just found.
        warnings.append(
            "This video is fairly low resolution, so some of the finer measurements may be "
            "less reliable than usual."
        )

    if not facts.person_check_ran:
        warnings.append(
            "Whether anybody is visible could not be checked on this machine, so the "
            "analysis may find nothing to measure."
        )
    elif facts.frames_checked == 0:
        warnings.append("No frames could be sampled to check whether anybody is visible.")
    else:
        seen = facts.frames_with_person / facts.frames_checked
        if seen < PERSON_CHECK_MIN_RATE:
            return Validation(
                ok=False,
                code="no_person",
                reason=(
                    "Nobody could be seen in this video. Check that the camera was pointing "
                    "at you and that your head and shoulders are in shot."
                ),
                warnings=tuple(warnings),
                **measurements,
            )
        if seen < 1.0:
            warnings.append(
                "You were not visible in every frame that was checked. The analysis will "
                "still run, and it lowers its own confidence where it cannot see you."
            )

    # Only one person is ever measured, and the detector cannot tell us whether a second one
    # was there. Saying so up front is the only honest handling of it.
    warnings.append(
        "Only one person is analysed. If more than one is in shot the results will be "
        "unreliable."
    )

    return Validation(ok=True, code="ok", warnings=tuple(warnings), **measurements)


def _read_facts(video_path: str, check_person: bool = True) -> VideoFacts:
    """Open the file, measure it, and look at a few frames spread across it.

    OpenCV and the detector are imported inside this function rather than at the top of the
    file. That keeps the pure judgement above importable anywhere, including in tests and on
    a machine where neither is installed.
    """
    path = Path(video_path)
    if not path.exists():
        return VideoFacts(exists=False, opened=False)

    file_bytes = path.stat().st_size
    if file_bytes > MAX_FILE_BYTES:
        # Answer without opening it. Nothing further can be learned that would change the
        # verdict, and a file this large is slow even to start reading.
        return VideoFacts(exists=True, opened=False, file_bytes=file_bytes)

    try:
        import cv2
    except ImportError as exc:
        # Not a verdict on the video, so it must not be returned as one. Without the video
        # library nothing here can even look at the file, and calling that "unreadable"
        # would blame the user's recording for a missing piece of this program. Raising
        # instead lets the caller report that the check did not happen, which is the truth.
        raise RuntimeError(
            "Videos cannot be checked on this machine because the video library is not "
            "installed."
        ) from exc

    capture = cv2.VideoCapture(str(path))
    try:
        if not capture.isOpened():
            return VideoFacts(exists=True, opened=False, file_bytes=file_bytes)

        source_fps = capture.get(cv2.CAP_PROP_FPS) or 0.0
        total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))

        # Reporting properties is not the same as being decodable. Plenty of broken files
        # will happily describe themselves and then fail on the first frame, so the only
        # convincing proof the file is usable is a frame that actually comes out of it.
        ok, first_image = capture.read()
        if not ok or first_image is None:
            return VideoFacts(exists=True, opened=False, file_bytes=file_bytes)

        duration_s = total_frames / source_fps if source_fps and total_frames else 0.0
        facts = VideoFacts(
            exists=True,
            opened=True,
            file_bytes=file_bytes,
            duration_s=duration_s,
            width=width,
            height=height,
            source_fps=source_fps,
            total_frames=total_frames,
        )

        if not check_person:
            return facts

        images = _sample_spread(capture, first_image, total_frames, cv2)
        checked, with_person = _count_frames_with_a_person(images)
        if checked < 0:
            return facts  # the detector was not available, so the check never ran
        return facts._replace(
            person_check_ran=True,
            frames_checked=checked,
            frames_with_person=with_person,
        )
    finally:
        capture.release()


def _sample_spread(capture, first_image, total_frames: int, cv2) -> list:
    """Collect a handful of frames from across the whole clip, not just the opening.

    Jumping around the video is normally avoided, because the detector follows the subject
    from one frame to the next and seeking throws that tracking away. Here it is exactly
    right: each frame is judged on its own, and taking them from throughout the clip is what
    stops a video where the subject arrives late from being rejected on its first second.
    """
    images = [first_image]
    if total_frames <= 1:
        return images

    step = max(1, total_frames // PERSON_CHECK_FRAMES)
    for index in range(step, total_frames, step):
        if len(images) >= PERSON_CHECK_FRAMES:
            break
        capture.set(cv2.CAP_PROP_POS_FRAMES, index)
        ok, image = capture.read()
        if ok and image is not None:
            images.append(image)
    return images


def _count_frames_with_a_person(images: list) -> tuple[int, int]:
    """Count how many of the given frames have somebody visible in them.

    Returns how many frames were looked at and how many had somebody in them, or minus one
    for the count when the detector is not installed, which the caller treats as the check
    not having happened rather than as nobody being there. Those two are very different and
    must never be confused: one is a fact about the video, the other is a fact about the
    machine it is being checked on.

    A frame counts as containing somebody if either the body or the face was found. Either
    one on its own is proof a person is there, and requiring both would turn an ordinary
    moment of looking down at notes into evidence of an empty room.

    The frames are treated as unrelated still images rather than as video, because they were
    taken from all over the clip and there is no continuity between them to track.
    """
    try:
        from detection.holistic import HolisticDetector
    except ImportError:
        return -1, 0

    try:
        # The same model the real analysis uses, and deliberately so. The lighter, faster
        # model would be the obvious choice for a check that only looks at eight frames, but
        # it is not shipped inside the library: asking for it makes the library fetch it
        # over the internet the first time. This program is required to work with no network
        # at all, so the only safe choice is the model that is already on disk. On eight
        # frames the difference in speed is not worth noticing anyway.
        with HolisticDetector(model_complexity=1, static_image_mode=True) as detector:
            found = 0
            for image in images:
                channels = detector.detect(image)
                if channels["pose"]["detected"] or channels["face"]["detected"]:
                    found += 1
            return len(images), found
    except Exception:  # noqa: BLE001
        # Anything at all going wrong inside the detector means the check did not happen.
        # It must not be reported as an empty room, and it must not stop the user: the file
        # may well be fine, and the analysis itself will fail loudly enough if it is not.
        return -1, 0


def validate_video(
    video_path: str,
    min_duration_s: float = DEFAULT_MIN_DURATION_S,
    check_person: bool = True,
) -> Validation:
    """Check one file and say whether it can be analysed."""
    return judge(_read_facts(video_path, check_person=check_person), min_duration_s)


def as_json(result: Validation) -> dict:
    """The verdict in the shape the desktop application reads.

    The names change from the underscored style Python uses to the run-together style the
    application side uses, in the same way every other message crossing between the two
    does. Keeping that consistent matters more than either convention does on its own.
    """
    return {
        "ok": result.ok,
        "code": result.code,
        "reason": result.reason,
        "durationS": round(result.duration_s, 1),
        "width": result.width,
        "height": result.height,
        "sourceFps": round(result.source_fps, 2),
        "warnings": list(result.warnings),
    }
