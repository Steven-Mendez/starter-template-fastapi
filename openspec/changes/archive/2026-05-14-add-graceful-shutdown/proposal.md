## Why

`Makefile:dev` runs `uv run fastapi dev … --host 0.0.0.0 --port $PORT` with no `--timeout-graceful-shutdown`. `src/worker.py:129-137` defines `WorkerSettings` with `on_startup` but no `on_shutdown` — in-flight arq jobs and the half-claimed outbox batch in `DispatchPending` are cancelled mid-transaction when SIGTERM lands. The DB engine is also never disposed on shutdown, leaving connections hanging until socket TTL.

## What Changes

- Add `APP_SHUTDOWN_TIMEOUT_SECONDS` (default 30 s) used by both processes.
- Document `uvicorn ... --timeout-graceful-shutdown 30` in `docs/operations.md` and bake it into the production `Dockerfile` `CMD`. Also document the matching K8s `terminationGracePeriodSeconds: 35`.
- Add `on_shutdown` to `arq.WorkerSettings` (`src/worker.py`):
  - Wait for the current relay tick + any active job handlers to finish, bounded by `APP_SHUTDOWN_TIMEOUT_SECONDS`.
  - Dispose the SQLAlchemy engine.
  - Close the Redis client.
- Add a FastAPI `lifespan` finalizer that:
  - Clears the readiness flag so `/health/ready` returns 503 while in-flight requests drain.
  - Disposes the engine.
  - Closes Redis.
  - Flushes the OTel `BatchSpanProcessor` (`provider.shutdown()`).

**Capabilities — Modified**: `project-layout`.

## Impact

- **Code**:
  - `src/worker.py` (add `on_shutdown`).
  - `src/main.py` (lifespan finalizer block).
  - `src/app_platform/config/sub_settings.py` (new `APP_SHUTDOWN_TIMEOUT_SECONDS` field on the platform settings projection).
  - `src/app_platform/observability/tracing.py` (expose `provider` for `shutdown()` in the finalizer).
  - `Dockerfile` `CMD` for both runtime stages (`runtime`, `runtime-worker`).
  - `docs/operations.md` (shutdown ordering, K8s budget).
- **Tests**: a manual smoke checklist (SIGTERM mid-relay → assert no half-committed rows; SIGTERM mid-request → assert the request completes before exit).
