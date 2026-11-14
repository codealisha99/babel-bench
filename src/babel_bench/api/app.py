"""FastAPI application: the playground endpoints. Served as `babel_bench.api.app:app`."""

from __future__ import annotations

import os

from fastapi import Depends, FastAPI, HTTPException, Path, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field

from . import views
from .config import MAX_SEED, Settings
from .guard import Busy, BodyLimit, ConcurrencyGate, RateLimiter, client_ip
from .sandbox import SandboxFailure, SandboxTimeout, run_grade


class RunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    seed: int = Field(ge=0, le=MAX_SEED)
    task_id: str = Field(min_length=1, max_length=64)
    program: str = Field(min_length=1)


ON_VERCEL = bool(os.environ.get("VERCEL"))  # set by the Vercel runtime, never by a client


def create_app(settings: Settings) -> FastAPI:
    app = FastAPI(title="babel-bench playground", docs_url=None, redoc_url=None, openapi_url=None)
    reads = RateLimiter(settings.reads_per_minute)
    runs = RateLimiter(settings.runs_per_minute)
    gate = ConcurrencyGate(settings.max_concurrent_runs)

    def limit(limiter: RateLimiter):
        def check(request: Request) -> None:
            key = client_ip(request.headers, request.client.host if request.client else None,
                            on_vercel=ON_VERCEL)
            if not limiter.allow(key):
                raise HTTPException(429, "too many requests, slow down", headers={"Retry-After": "60"})
        return check

    read_limit, run_limit = Depends(limit(reads)), Depends(limit(runs))
    seed_path = Path(ge=0, le=MAX_SEED)

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.get("/api/languages/{seed}", dependencies=[read_limit])
    def language(seed: int = seed_path) -> dict:
        return views.language(seed)

    @app.get("/api/languages/{seed}/tasks", dependencies=[read_limit])
    def tasks(seed: int = seed_path) -> dict:
        return views.tasks(seed)

    @app.post("/api/run", dependencies=[run_limit])
    def run(body: RunRequest) -> dict:
        if len(body.program) > settings.max_program_chars:
            raise HTTPException(413, f"program over {settings.max_program_chars} characters")
        task = views.find_task(body.task_id)
        if task is None:
            raise HTTPException(404, "unknown task")
        if task.tier == "predict":
            raise HTTPException(400, "predict tasks are answered by typing the output, not by running code here")
        request = {"seed": body.seed, "task_id": body.task_id, "program": body.program}
        try:
            with gate.slot():
                result = run_grade(request, settings.run_timeout_s)
        except Busy as exc:
            raise HTTPException(503, "the grader is busy, try again in a few seconds") from exc
        except SandboxTimeout as exc:
            raise HTTPException(504, "your program did not finish in time") from exc
        except SandboxFailure as exc:
            raise HTTPException(500, "the grader failed on this program") from exc
        return {"seed": body.seed, "task_id": body.task_id, **result}

    app.add_middleware(BodyLimit, max_bytes=settings.max_body_bytes)
    app.add_middleware(
        CORSMiddleware, allow_origins=list(settings.allowed_origins),
        allow_methods=["GET", "POST"], allow_headers=["Content-Type"],
    )
    return app


app = create_app(Settings.from_env())
