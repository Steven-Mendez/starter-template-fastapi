## 1. Implementation

- [x] 1.1 Add a `ready: asyncio.Event` (or boolean on `app.state`) toggled in `src/main.py`'s lifespan when sealing finishes.
- [x] 1.2 Create `src/app_platform/api/health.py` with the `/health/ready` route handler and one async probe function per dependency.
- [x] 1.3 Mount the router from `src/app_platform/api/root.py`.
- [x] 1.4 In `src/app_platform/api/health.py`, wrap each probe with `asyncio.wait_for(probe(), timeout=settings.health_ready_probe_timeout_seconds)` and run them in parallel via `asyncio.gather(..., return_exceptions=True)`.
- [x] 1.4a On timeout or exception, log at WARN with the dependency name and exception class; report the dep as `{"<dep>": "fail", "reason": "<short str>"}` in the JSON body.
- [x] 1.4b When any dep fails, set HTTP status to 503 and add `Retry-After: 1` to the response headers.
- [x] 1.5 Add `health_ready_probe_timeout_seconds: float = 1.0` (env `APP_HEALTH_READY_PROBE_TIMEOUT_SECONDS`) to `ObservabilitySettings` in `src/app_platform/config/sub_settings.py` (after `metrics_enabled`); thread it through `from_app_settings` and add a `0.0 < v <= 30.0` range check in `validate(errors)`.
- [x] 1.6 In `src/app_platform/api/health.py`, return `{"status":"starting"}` with 503 (and no `Retry-After`) when the lifespan-ready flag on `app.state` is unset or False; bypass dependency probes entirely.

## 2. Tests

- [x] 2.1 Unit (`src/app_platform/tests/unit/api/test_health_ready.py`): healthy DB + Redis → 200 with all deps `ok`.
- [x] 2.2 Unit: DB probe raises → 503 with `db` named in body and `Retry-After: 1` header.
- [x] 2.3 Unit: `/health/ready` before lifespan completes → 503 `{"status":"starting"}` and no `Retry-After`.
- [x] 2.4 Unit: Redis probe exceeds `health_ready_probe_timeout_seconds` → 503 with `redis` named and timeout reason.
- [x] 2.5 Unit: no Redis URL configured → `/health/ready` body's `deps` mapping contains no `redis` key.

## 3. Wrap-up

- [x] 3.1 Update `docs/observability.md` with the new probe and how it differs from `/health/live`.
- [x] 3.2 `make ci` green.
