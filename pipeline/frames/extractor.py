"""Pulling frames out of a video, but only as many as are actually needed.

Detection is slow, so BodyTalk never looks at every frame. It takes roughly six a second.
That is enough to keep a three minute clip processing in a reasonable time on an ordinary
laptop, while still being fine-grained enough for what the feedback rules need. Those rules
look for behaviour that carries on for several seconds, not for single moments, so
inspecting every frame would cost a great deal of time and change none of the answers.

Sampling here means reading through every frame in the file but only handing every Nth one
to the detector. N is the stride. A video recorded at 30 frames a second with a target of
six gives a stride of 5, so frames 0, 5, 10 and so on get looked at.

OpenCV is imported inside each function rather than at the top of the file. That way the
self-test in run.py still works on a machine where OpenCV was never installed, which is the
entire point of having a self-test.
"""

from __future__ import annotations

from typing import Iterator, NamedTuple


class VideoInfo(NamedTuple):
    """What we can learn about a video before decoding any of it."""

    width: int
    height: int
    source_fps: float  # the rate the file was recorded at
    total_frames: int
    duration_s: float
    stride: int  # look at every Nth frame
    analysis_fps: float  # the rate actually achieved, which is source_fps divided by stride


class SampledFrame(NamedTuple):
    """One frame on its way to the detector, tagged with where it came from."""

    index: int  # the frame's number in the original video, not a count of samples
    t_s: float  # when it occurs, in seconds
    image: object  # the decoded image, in the colour order OpenCV uses


def _stride_for(source_fps: float, target_fps: float) -> int:
    """Work out how many frames to skip to get near the target rate.

    Never returns less than 1, because there is no way to sample a video more often than
    it was recorded. Asking for 30 a second from a 24 a second clip just gets you 24.
    """
    if target_fps <= 0:
        return 1
    return max(1, round(source_fps / target_fps))


def probe(video_path: str, fps: float = 6.0) -> VideoInfo:
    """Open the video just long enough to read its properties, then close it again.

    Raises a plain-language error if the file cannot be decoded. The caller turns that
    into the message shown to the user, so it is written to be readable rather than
    technical.
    """
    import cv2

    cap = cv2.VideoCapture(video_path)
    try:
        if not cap.isOpened():
            raise ValueError(f"This file could not be read as a video: {video_path}")

        # Not every video file reports these honestly, so fall back to something sensible
        # rather than dividing by zero further down.
        source_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    finally:
        cap.release()

    duration_s = total_frames / source_fps if source_fps else 0.0
    stride = _stride_for(source_fps, fps)

    return VideoInfo(
        width=width,
        height=height,
        source_fps=source_fps,
        total_frames=total_frames,
        duration_s=duration_s,
        stride=stride,
        analysis_fps=source_fps / stride,
    )


def expected_sample_count(info: VideoInfo) -> int:
    """Roughly how many frames will be sampled, which is what sizes the progress bar.

    Returns 0 if the file never reported how many frames it has. Callers should treat that
    as genuinely unknown and say so, rather than showing a percentage that is made up.
    """
    if info.total_frames <= 0:
        return 0
    return (info.total_frames + info.stride - 1) // info.stride


def sample_frames(
    video_path: str,
    fps: float = 6.0,
    max_frames: int = 0,
) -> Iterator[SampledFrame]:
    """Hand back frames at roughly the requested rate, in order, one at a time.

    Written as a generator, so memory use stays flat however long the clip is. Setting
    `max_frames` above zero stops early, which is useful when checking something quickly
    without waiting for a whole video.

    The frames come out in order and that matters. MediaPipe follows the subject from one
    frame to the next while it works, so jumping around the video would throw away the
    smoothing that tracking gives and make the landmarks jumpier than they need to be.
    """
    import cv2

    info = probe(video_path, fps)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"This file could not be read as a video: {video_path}")

    try:
        frame_index = -1
        sampled = 0
        while True:
            ok, image = cap.read()
            if not ok:
                break  # the end of the file, or a frame that would not decode
            frame_index += 1

            if frame_index % info.stride != 0:
                continue  # not one of the frames being sampled

            yield SampledFrame(
                index=frame_index,
                t_s=frame_index / info.source_fps,
                image=image,
            )

            sampled += 1
            if max_frames and sampled >= max_frames:
                break
    finally:
        cap.release()
