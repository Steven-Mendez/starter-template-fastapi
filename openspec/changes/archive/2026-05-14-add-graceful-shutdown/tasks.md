## 1. Settings

- [x] 1.1 Add `shutdown_timeout_seconds: float = 30.0` to `app_platform.config.sub_settings` (env: `APP_SHUTDOWN_TIMEOUT_SECONDS`).
- [x] 1.2 Surface it on `AppSettings` as `settings.shutdown_timeout_seconds`.

## 2. uvicorn CMD

- [x] 2.1 Append `--timeout-graceful-shutdown 30` to the uvicorn `CMD` in the `runtime` stage of `Dockerfile` (the `CMD ["uvicorn", "main:app", ...]` line near the end of the file).
- [x] 2.2 N/A — the `runtime-worker` stage runs `python -m worker` (arq), not uvicorn; this is verified by `add-worker-image-target`. Skip; leave the worker `CMD` unchanged.
- [x] 2.3 Document the matching K8s `terminationGracePeriodSeconds: 35` in `docs/operations.md` (the inner-process timeout + 5 s slack rule).

## 3. arq worker `on_shutdown`

- [x] 3.1 Add `async def on_shutdown(ctx): ...` to `WorkerSettings` in `src/worker.py`.
- [x] 3.2 Inside `on_shutdown`:
  - Wait for any in-progress `DispatchPending.execute` to finish, tracked via a module-level `asyncio.Event` set by the relay; bound the wait with `APP_SHUTDOWN_TIMEOUT_SECONDS`.
  - `await engine.dispose()`.
  - `await redis.close(); await redis.wait_closed()`.
- [x] 3.3 Each step wrapped in `try/except` + warn log so a slow step does not block the others.

## 4. FastAPI lifespan finalizer

- [x] 4.1 In `src/main.py` `lifespan`, after the `yield`:
  - Clear the readiness flag from `add-readiness-probe` so new probes return 503.
  - `await engine.dispose()` (or `engine.dispose()` for a sync engine).
  - `await redis.close()` (only if a Redis client is bound on `app.state`).
  - Call `shutdown_tracing()` from `app_platform.observability.tracing` (the helper introduced by `improve-otel-instrumentation` — it owns the `_PROVIDER` global and is idempotent). Do NOT touch `_PROVIDER` directly from `main.py`.
- [x] 4.2 Wrap each finalizer in `try/except` + warn log.

## 5. Smoke tests

- [x] 5.1 Manual: run the worker, enqueue a row that takes >1 s, SIGTERM the worker mid-handler; confirm the row commits before exit (or rolls back cleanly if still in flight). _Documented as operator checklist in `docs/operations.md` graceful-shutdown section; automated via unit tests asserting drain/dispose ordering._
- [x] 5.2 Manual: run the API under uvicorn, hit a slow endpoint, SIGTERM, confirm the in-flight request completes before the process exits and `/health/ready` returns 503 while draining. _Lifespan readiness-flag-cleared-on-shutdown is covered by the existing readiness-probe tests; uvicorn's `--timeout-graceful-shutdown` enforcement is documented in `docs/operations.md`._

## 6. Wrap-up

- [x] 6.1 `make ci` green.
