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

# ---------------------------------------------------------------------------
# Builder stages — one per process role.
#
# After ``trim-runtime-deps`` the API and worker have disjoint runtime
# dep sets: the API needs ``fastapi[standard]``; the worker extra
# carries ``redis`` (and not ``fastapi[standard]``). ``arq`` was
# removed in ROADMAP ETAPA I step 5 — the production worker runtime
# (AWS SQS + a Lambda worker) arrives at ROADMAP steps 26-27; the
# stage is kept because step 27 revives it. We build two prebuilt
# ``/app/.venv`` directories so each role's runtime image carries only
# its own wheels. See docs/operations.md.
# ---------------------------------------------------------------------------

FROM base AS builder-api

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project --extra api

COPY alembic.ini ./
COPY alembic ./alembic
COPY src ./src

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --extra api

FROM base AS builder-worker

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project --extra worker

COPY alembic.ini ./
COPY alembic ./alembic
COPY src ./src

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --extra worker

# ---------------------------------------------------------------------------
# Legacy ``builder`` alias.
#
# Older docs / external scripts may still refer to the ``builder`` stage
# by name. Alias it to ``builder-api`` so those callers keep working;
# new callers should use ``builder-api`` / ``builder-worker`` directly.
# ---------------------------------------------------------------------------
FROM builder-api AS builder

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

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--no-server-header", "--reload", "--reload-dir", "/app/src", "--reload-exclude", "**/tests/**"]

# ---------------------------------------------------------------------------
# Runtime base — shared hardening for every deployable role.
#
# Extracted so ``runtime`` (API) and ``runtime-worker`` (background
# worker) can each pull their own builder venv while sharing the
# digest-pinned base, tini PID-1, and the UID/GID 10001 contract.
# ---------------------------------------------------------------------------
FROM python:3.12-slim@sha256:401f6e1a67dad31a1bd78e9ad22d0ee0a3b52154e6bd30e90be696bb6a3d7461 AS runtime-base

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

ENTRYPOINT ["tini", "--"]

# ---------------------------------------------------------------------------
# API runtime — carries ``fastapi[standard]`` (and uvicorn/starlette
# extras + python-multipart transitively).
# ---------------------------------------------------------------------------
FROM runtime-base AS runtime

COPY --chown=app:app --from=builder-api /app /app

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c \
    "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/live').read()" \
    || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--no-server-header", "--timeout-graceful-shutdown", "30"]

# ---------------------------------------------------------------------------
# Worker stage
#
# Extends ``runtime-base`` (not ``runtime``) so the worker image does
# NOT inherit the API's ``fastapi[standard]`` venv. The worker pulls
# the prebuilt venv from ``builder-worker`` instead — ``redis`` and
# the shared core deps.
#
# The worker *runtime* is not wired: ``arq`` was removed in ROADMAP
# ETAPA I step 5; the production worker runtime (AWS SQS + a Lambda
# worker) arrives at ROADMAP steps 26-27. ``python -m worker`` builds
# the composition scaffold and exits non-zero with a clear "no job
# runtime wired" message — the image builds, the container exits
# loudly. The stage is intentionally kept (step 27 revives it); do
# NOT delete it.
#
# Build with:  docker build --target runtime-worker -t worker:latest .
# ---------------------------------------------------------------------------
FROM runtime-base AS runtime-worker

COPY --chown=app:app --from=builder-worker /app /app

USER app

# The worker exposes no TCP listener and has no HEALTHCHECK; rely on
# the orchestrator's exit-code-based liveness instead. ``redis-cli`` is
# not on ``python:3.12-slim`` and pulling it in only for HEALTHCHECK is
# overkill.

CMD ["python", "-m", "worker"]
