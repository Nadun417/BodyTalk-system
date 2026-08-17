"""Put the Python pipeline package on sys.path so `from fusion import ...` resolves
when pytest is run from the repo root."""

import os
import sys

PIPELINE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "pipeline"))
if PIPELINE_DIR not in sys.path:
    sys.path.insert(0, PIPELINE_DIR)
