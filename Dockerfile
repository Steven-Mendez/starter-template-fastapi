# syntax=docker/dockerfile:1.7

FROM python:3.12-slim@sha256:401f6e1a67dad31a1bd78e9ad22d0ee0a3b52154e6bd30e90be696bb6a3d7461 AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:0.11.8@sha256:3b7b60a81d3c57ef471703e5c83fd4aaa33abcd403596fb22ab07db85ae91347 /uv /uvx /bin/
COPY pyproject.toml uv.lock README.md ./

FROM base AS builder

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY alembic.ini ./
COPY alembic ./alembic
COPY src ./src

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

FROM base AS dev

ENV PATH="/app/.venv/bin:$PATH"

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project

COPY alembic.ini ./
COPY alembic ./alembic
COPY src ./src

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--reload-dir", "/app/src", "--reload-exclude", "**/tests/**"]

FROM python:3.12-slim@sha256:401f6e1a67dad31a1bd78e9ad22d0ee0a3b52154e6bd30e90be696bb6a3d7461 AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# tini is the PID-1 signal forwarder + zombie reaper. The HEALTHCHECK below
# spawns a `python -c` subprocess; without tini, defunct children accumulate.
RUN apt-get update \
    && apt-get install -y --no-install-recommends tini \
    && rm -rf /var/lib/apt/lists/*

# Explicit UID/GID 10001 — the contract for K8s securityContext.runAsUser /
# fsGroup. Well above default system UIDs so it won't collide with the base
# image's reserved users.
RUN addgroup --system --gid 10001 app \
    && adduser --system --uid 10001 --ingroup app app

COPY --chown=app:app --from=builder /app /app

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c \
    "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/live').read()" \
    || exit 1

ENTRYPOINT ["tini", "--"]

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-graceful-shutdown", "30"]

# ---------------------------------------------------------------------------
# Worker stage
#
# Extends ``runtime`` so the worker image inherits every hardening layer
# (digest-pinned base, tini PID 1, UID/GID 10001, the prebuilt /app/.venv
# from ``builder``). Only the CMD (and HEALTHCHECK) differ — the worker
# has no HTTP listener, so the API liveness probe must not be inherited.
#
# Build with:  docker build --target runtime-worker -t worker:latest .
# ---------------------------------------------------------------------------
FROM runtime AS runtime-worker

# The worker exposes no TCP listener. Clearing the inherited HEALTHCHECK
# prevents the orchestrator from probing http://localhost:8000/health/live
# against a process that will never answer. ``redis-cli`` is not present
# on ``python:3.12-slim`` and pulling it in only for HEALTHCHECK is
# overkill; rely on the orchestrator's exit-code-based liveness instead.
HEALTHCHECK NONE

# The worker does not bind a TCP listener; the inherited ``EXPOSE 8000``
# from the ``runtime`` stage is harmless metadata and is left in place
# (Docker provides no directive to revoke an exposed port from a parent).

CMD ["python", "-m", "worker"]
