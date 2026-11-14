"""Vercel entry point for the playground API. The function runs `app` from the source tree in src/."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from babel_bench.api.app import app  # noqa: E402,F401
