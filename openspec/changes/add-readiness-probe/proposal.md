## Why

`src/app_platform/api/root.py:23` defines `/health/live` but no `/health/ready`. The tracing/metrics URL exclusion lists already reference `/health/ready` (so they expect it), but the route is never registered. K8s rolling deploys will route traffic the moment the process accepts TCP — before DB warm-up or registry sealing — and after a Postgres restart the pod will never drop out of rotation. There's also no readiness signal during outbox-registry sealing.

## What Changes

- Add `GET /health/ready` running, in parallel:
  - `SELECT 1` against the engine.
  - `redis.ping()` when `APP_AUTH_REDIS_URL` (or `APP_JOBS_REDIS_URL`) is set.
  - `head_bucket` when `APP_STORAGE_ENABLED=true` and `APP_STORAGE_BACKEND=s3`.
- Each probe has a per-dependency timeout (default 1.0 s, overridable via `APP_HEALTH_READY_PROBE_TIMEOUT_SECONDS`).
- Returns `200 {"status":"ok", "deps": {...}}` when all configured dependencies are healthy; `503` with the failing dependency named (and `Retry-After: 1`) otherwise.
- Until the FastAPI lifespan completes (registries sealed, containers built) `/health/ready` returns `503 {"status":"starting"}`.
- `/health/live` stays a process-only check (no dependencies); it remains the kubelet liveness target.

**Capabilities — Modified**: `project-layout` (platform health probes).

## Impact

- **Code**:
  - `src/app_platform/api/health.py` (new) — probe functions and the `/health/ready` route.
  - `src/app_platform/api/root.py` — mounts the new router; no other change.
  - `src/main.py` — sets / clears a small `AppState.ready: asyncio.Event` (or a flag on `app.state`) in the lifespan.
  - `src/app_platform/config/sub_settings.py` — adds `APP_HEALTH_READY_PROBE_TIMEOUT_SECONDS` (default 1.0).
  - `docs/observability.md` — documents the new probe.
- **Migrations / production**: none.
- **Tests**: 3 unit tests (healthy, DB down, lifespan-not-yet-done).
