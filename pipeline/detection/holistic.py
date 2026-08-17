"""Running MediaPipe over each frame to find the face, body and hand landmarks.

This is where pixels become numbers. Everything after it, the three channel analysers, the
weighting and the feedback, works from what this file produces and never touches the video
again.

Something the proof of concept turned up, which shapes how this file is written:

All four channels come back in the same format, and every landmark in that format has a
visibility field attached. It would be easy to assume all four therefore report how clearly
they were seen. They do not. Only the body pose fills that field in. Face and hand landmarks
come back with visibility sitting at exactly zero whether they were seen perfectly or barely
at all, which is worse than useless, because zero also happens to be what genuinely invisible
looks like.

So this file records the visibility number only for the pose, where it means something, and
for the other channels records nothing more than whether they were found. The analysers work
out a stand-in for face and hand visibility from that, based on how often each was detected.

On which version of MediaPipe is used: the older Holistic solution is on its way out in
recent releases, but it is the one the proof of concept confirmed working on this machine,
and it returns all four channels from a single call while keeping track of the subject
between frames. The newer approach would mean running three separate detectors and stitching
their output together. Staying on what has been shown to work, and if that ever has to change
it only affects this one class.

MediaPipe is imported inside the functions so the self-test in run.py can run without it.
"""

from __future__ import annotations

from typing import Any

#: Coordinates come back as fractions of the frame rather than pixels, so five decimal
#: places is finer than a single pixel even on a 4K image. Rounding at this point roughly
#: halves the size of the saved landmark file and changes no measurement that reads it.
_COORD_DP = 5


def _xyz(landmark_list: Any) -> list[list[float]]:
    """Face and hand landmarks, as x, y and z. Visibility is left out because it is never real."""
    return [
        [round(lm.x, _COORD_DP), round(lm.y, _COORD_DP), round(lm.z, _COORD_DP)]
        for lm in landmark_list.landmark
    ]


def _xyzv(landmark_list: Any) -> list[list[float]]:
    """Body pose landmarks, as x, y, z and visibility.

    That fourth number is the genuine measure of how clearly each point was seen, and it is
    the only place in the whole pipeline where it comes straight from the detector. It is
    the reason the pose channel can weight itself honestly while the face and hands have to
    fall back on a stand-in.
    """
    return [
        [
            round(lm.x, _COORD_DP),
            round(lm.y, _COORD_DP),
            round(lm.z, _COORD_DP),
            round(lm.visibility, _COORD_DP),
        ]
        for lm in landmark_list.landmark
    ]


def _channel(landmark_list: Any, encode) -> dict:
    """Build one channel's entry in a frame record.

    Always the same two keys, whether anything was found or not. Code further down can then
    read the record without first checking whether a field exists, which is the kind of
    small inconsistency that causes awkward bugs later.
    """
    if landmark_list is None:
        return {"detected": False, "landmarks": None}
    return {"detected": True, "landmarks": encode(landmark_list)}


def mediapipe_version() -> str:
    """The MediaPipe version, recorded alongside the landmarks so results stay reproducible."""
    import mediapipe as mp

    return getattr(mp, "__version__", "unknown")


class HolisticDetector:
    """Runs detection over frames one at a time, keeping track between them.

    Use it with a `with` block so the detector is always shut down properly:

        with HolisticDetector() as detector:
            for frame in sample_frames(path):
                record = detector.detect(frame.image)

    Frames have to be fed in order. The detector follows the person from one frame to the
    next, and feeding them out of order throws that away.
    """

    def __init__(
        self,
        model_complexity: int = 1,
        refine_face_landmarks: bool = False,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
    ) -> None:
        import mediapipe as mp

        self.model_complexity = model_complexity
        # Leaving this off keeps the face mesh at 468 points, which is what the saved
        # landmark files are built around. Turning it on adds 10 iris points and would make
        # every file already on disk inconsistent with any new ones.
        self.refine_face_landmarks = refine_face_landmarks

        self._holistic = mp.solutions.holistic.Holistic(
            static_image_mode=False,  # treat the input as video, so it tracks between frames
            model_complexity=model_complexity,
            refine_face_landmarks=refine_face_landmarks,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )

    def detect(self, frame_bgr: Any) -> dict:
        """Run detection on one frame and return the four channel entries.

        The caller adds the frame number and timestamp around this before saving it.
        """
        import cv2

        # An easy one to get wrong: OpenCV hands back images with the colour channels in
        # the order blue, green, red, while MediaPipe expects red, green, blue. Skip this
        # and detection still runs, it just quietly performs worse.
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        rgb.flags.writeable = False  # lets MediaPipe avoid making its own copy

        results = self._holistic.process(rgb)

        return {
            "face": _channel(results.face_landmarks, _xyz),
            "pose": _channel(results.pose_landmarks, _xyzv),
            "leftHand": _channel(results.left_hand_landmarks, _xyz),
            "rightHand": _channel(results.right_hand_landmarks, _xyz),
        }

    def close(self) -> None:
        self._holistic.close()

    def __enter__(self) -> "HolisticDetector":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()
