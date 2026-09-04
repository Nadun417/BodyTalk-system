"""The analysis must never reach the network, and this proves it rather than assuming it.

Running entirely on the user's own machine is the promise this application is built around.
Practice interview videos are about as personal as a recording gets, and the whole design
follows from nothing ever leaving the computer. A promise like that is worth testing, because
it is the kind that breaks quietly: nobody notices a library quietly fetching something on a
machine that happens to be online, and the person who does notice is the one running it
offline for the first time, which is exactly the person being promised to.

This has already happened once. The check that decides whether anybody is visible in a video
was first written with MediaPipe's lightest pose model, which is not shipped inside the
library and is fetched over the internet the first time it is used. It was caught by seeing
the word "Downloading" on a terminal, not by any test. That is what these tests are for.

**How they work.** Making a network connection at all, in any Python library, ends up calling
`connect` on a socket. These tests replace that one function with one that refuses and records
the attempt, then run the real pipeline. If anything anywhere tries to reach out, the attempt
is recorded and the test fails with the address it was reaching for. Nothing is mocked beyond
that single function, so this is the real analysis running, not a stand-in for it.
"""

from __future__ import annotations

import socket
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "fixtures"


class NetworkWasUsed(AssertionError):
    """Raised the moment anything tries to open a connection."""


@pytest.fixture
def no_network(monkeypatch):
    """Cut the machine off for the duration of one test, and record any attempt to reach out.

    Everything that talks to a network in Python goes through a socket eventually, whichever
    library is doing the asking, so refusing at that level catches all of it: a model being
    downloaded, a version check, a telemetry ping. Connections to this same machine are left
    alone, because those are not the network leaving the building and some libraries use them
    internally.
    """
    attempts: list = []
    real_connect = socket.socket.connect

    def refuse(self, address, *args, **kwargs):
        host = address[0] if isinstance(address, tuple) else str(address)
        if host in ("127.0.0.1", "::1", "localhost"):
            return real_connect(self, address, *args, **kwargs)
        attempts.append(address)
        raise NetworkWasUsed(f"Something tried to reach {address!r}")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket.socket, "connect_ex", refuse)
    return attempts


def test_importing_the_pipeline_reaches_nowhere(no_network):
    """Loading the analysis code should not, by itself, phone anywhere.

    Worth its own test because an import is the easiest place for this to go wrong and the
    hardest to notice: a library that checks for a newer version or registers itself when it
    loads does so before a single frame has been looked at.
    """
    for module in ("pipeline", "detection.holistic", "validation", "fusion", "feedback.rules"):
        sys.modules.pop(module, None)

    import pipeline  # noqa: F401
    import validation  # noqa: F401
    from fusion import make_strategy

    make_strategy("adaptive")
    assert no_network == []


@pytest.mark.skipif(
    not (FIXTURES / "landmarks" / "calib-still.landmarks.jsonl").exists(),
    reason="needs the cached landmarks for a practice clip",
)
def test_a_whole_analysis_reaches_nowhere(no_network, tmp_path):
    """Analyse a real recording end to end with the network cut off.

    This runs from the cached landmarks rather than from the video, so it exercises the
    scoring, the fusion and the feedback without waiting for detection. Detection itself is
    covered by the model test below, which is where the one real incident happened.
    """
    from fusion import make_strategy
    from pipeline import Pipeline

    result = Pipeline(make_strategy("adaptive")).run(
        str(FIXTURES / "calib-still.mp4"),
        fps=6.0,
        out_dir=str(tmp_path),
        reuse_cache=True,
    )

    assert result["overallScore"] is not None
    assert no_network == []


@pytest.mark.skipif(
    not (FIXTURES / "calib-still.mp4").exists(), reason="needs a practice clip to look at"
)
def test_the_detector_carries_its_own_model(no_network):
    """Starting the detector must not fetch anything.

    This is the one that already caught a real fault. The model the detector uses has to be
    one that ships inside the library, because the first thing a user does on a machine with
    no internet is open a video, and a detector that wanted to download something would fail
    there with nothing on screen explaining why.
    """
    pytest.importorskip("mediapipe", reason="MediaPipe is not installed here")
    numpy = pytest.importorskip("numpy")
    from detection.holistic import HolisticDetector

    # A blank frame is enough. The point is not what it finds but that starting the detector
    # and putting a frame through it loads every model it needs, which is the moment anything
    # missing would have to be fetched.
    blank = numpy.zeros((480, 640, 3), dtype=numpy.uint8)
    with HolisticDetector(static_image_mode=True) as detector:
        detector.detect(blank)

    assert no_network == []
