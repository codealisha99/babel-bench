"""Request guards: body size, per-IP rate limits, and a cap on concurrent grading runs."""

from __future__ import annotations

import threading
import time
from collections import deque
from collections.abc import Mapping
from contextlib import contextmanager

from starlette.responses import JSONResponse


class BodyLimit:
    """ASGI middleware. Requires a Content-Length no larger than max_bytes on body-carrying requests.

    Chunked bodies (no Content-Length) are refused, so the server never buffers an unbounded body.
    """

    def __init__(self, app, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in ("POST", "PUT", "PATCH"):
            await self.app(scope, receive, send)
            return
        headers = dict(scope["headers"])
        raw = headers.get(b"content-length")
        if raw is None:
            response = JSONResponse({"detail": "Content-Length header required"}, status_code=411)
        elif not raw.isdigit() or int(raw) > self.max_bytes:
            response = JSONResponse({"detail": f"request body over {self.max_bytes} bytes"}, status_code=413)
        else:
            await self.app(scope, receive, send)
            return
        await response(scope, receive, send)


class RateLimiter:
    """Sliding window: at most `limit` events per key in the last `window` seconds."""

    MAX_KEYS = 10_000

    def __init__(self, limit: int, window: float = 60.0, clock=time.monotonic) -> None:
        self.limit = limit
        self.window = window
        self.clock = clock
        self._hits: dict = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = self.clock()
        with self._lock:
            if len(self._hits) > self.MAX_KEYS:
                self._evict(now)
            hits = self._hits.setdefault(key, deque())
            while hits and now - hits[0] >= self.window:
                hits.popleft()
            if len(hits) >= self.limit:
                return False
            hits.append(now)
            return True

    def _evict(self, now: float) -> None:
        for key in [k for k, hits in self._hits.items() if not hits or now - hits[-1] >= self.window]:
            del self._hits[key]


class Busy(RuntimeError):
    """All grading slots are taken."""


class ConcurrencyGate:
    def __init__(self, slots: int) -> None:
        self._sem = threading.BoundedSemaphore(slots)

    @contextmanager
    def slot(self):
        if not self._sem.acquire(blocking=False):
            raise Busy("all grading slots are busy")
        try:
            yield
        finally:
            self._sem.release()


def client_ip(headers: Mapping, peer: str | None, on_vercel: bool = False) -> str:
    """The client IP as the edge proxy saw it.

    On Vercel, x-vercel-forwarded-for is set by the platform. It is trusted only when VERCEL is set,
    because elsewhere a client could send it to dodge the rate limit. Otherwise use the last
    X-Forwarded-For entry, since the proxy appends to it; this assumes one trusted proxy hop.
    """
    if on_vercel:
        platform_ip = headers.get("x-vercel-forwarded-for", "").strip()
        if platform_ip:
            return platform_ip
    forwarded = headers.get("x-forwarded-for", "")
    last = forwarded.split(",")[-1].strip() if forwarded else ""
    return last or peer or "unknown"
