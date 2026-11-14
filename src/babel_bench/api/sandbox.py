"""Run one grading request in a worker process, with a wall-clock limit enforced from outside."""

from __future__ import annotations

import json
import os
import subprocess
import sys

MAX_WORKER_BYTES = 64_000


class SandboxTimeout(RuntimeError):
    """The worker exceeded the wall-clock limit and was killed."""


class SandboxFailure(RuntimeError):
    """The worker crashed or returned something unreadable."""


def run_grade(request: dict, timeout_s: float) -> dict:
    # subprocess.run kills the child when the timeout expires. -I ignores PYTHON* variables and
    # the working directory, and the child gets an empty environment apart from PATH.
    try:
        proc = subprocess.run(
            [sys.executable, "-I", "-m", "babel_bench.api.worker"],
            input=json.dumps(request).encode("utf-8"), capture_output=True,
            timeout=timeout_s, check=False, env={"PATH": os.environ.get("PATH", "/usr/bin:/bin")},
        )
    except subprocess.TimeoutExpired as exc:
        raise SandboxTimeout(f"no result within {timeout_s:g} seconds") from exc
    if proc.returncode != 0 or len(proc.stdout) > MAX_WORKER_BYTES:
        raise SandboxFailure(f"worker exited with status {proc.returncode}")
    try:
        return json.loads(proc.stdout)
    except ValueError as exc:
        raise SandboxFailure("worker returned unreadable output") from exc
