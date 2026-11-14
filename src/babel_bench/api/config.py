"""Settings for the playground API. Every limit that protects the host is named here."""

from __future__ import annotations

import os
from dataclasses import dataclass

MAX_SEED = 99_999


@dataclass(frozen=True)
class Settings:
    allowed_origins: tuple = ()  # the landing page origin(s) allowed by CORS
    max_body_bytes: int = 16_384  # hard cap on any request body; chunked bodies are refused
    max_program_chars: int = 8_000
    run_timeout_s: float = 10.0  # wall-clock limit enforced by killing the worker process
    max_concurrent_runs: int = 3
    runs_per_minute: int = 20  # per client IP, for POST /api/run
    reads_per_minute: int = 120  # per client IP, for the GET endpoints

    @classmethod
    def from_env(cls, env=os.environ) -> Settings:
        raw = env.get("BABEL_ALLOWED_ORIGINS", "")
        origins = tuple(o.strip().rstrip("/") for o in raw.split(",") if o.strip())
        return cls(allowed_origins=origins)
