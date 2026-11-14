# Playground API: one small container, one worker process (the concurrency cap is per process).
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.7 /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

COPY pyproject.toml uv.lock .python-version ./
COPY src ./src
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn babel_bench.api.app:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
