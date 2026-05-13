## 1. Settings

- [ ] 1.1 Add `shutdown_timeout_seconds: float = 30.0` to `app_platform.config.sub_settings` (env: `APP_SHUTDOWN_TIMEOUT_SECONDS`).
- [ ] 1.2 Surface it on `AppSettings` as `settings.shutdown_timeout_seconds`.

## 2. uvicorn CMD

- [ ] 2.1 Append `--timeout-graceful-shutdown 30` to the uvicorn `CMD` in the `runtime` stage of `Dockerfile` (the `CMD ["uvicorn", "main:app", ...]` line near the end of the file).
- [ ] 2.2 N/A — the `runtime-worker` stage runs `python -m worker` (arq), not uvicorn; this is verified by `add-worker-image-target`. Skip; leave the worker `CMD` unchanged.
- [ ] 2.3 Document the matching K8s `terminationGracePeriodSeconds: 35` in `docs/operations.md` (the inner-process timeout + 5 s slack rule).

## 3. arq worker `on_shutdown`

- [ ] 3.1 Add `async def on_shutdown(ctx): ...` to `WorkerSettings` in `src/worker.py`.
- [ ] 3.2 Inside `on_shutdown`:
  - Wait for any in-progress `DispatchPending.execute` to finish, tracked via a module-level `asyncio.Event` set by the relay; bound the wait with `APP_SHUTDOWN_TIMEOUT_SECONDS`.
  - `await engine.dispose()`.
  - `await redis.close(); await redis.wait_closed()`.
- [ ] 3.3 Each step wrapped in `try/except` + warn log so a slow step does not block the others.

## 4. FastAPI lifespan finalizer

- [ ] 4.1 In `src/main.py` `lifespan`, after the `yield`:
  - Clear the readiness flag from `add-readiness-probe` so new probes return 503.
  - `await engine.dispose()` (or `engine.dispose()` for a sync engine).
  - `await redis.close()` (only if a Redis client is bound on `app.state`).
  - Call `shutdown_tracing()` from `app_platform.observability.tracing` (the helper introduced by `improve-otel-instrumentation` — it owns the `_PROVIDER` global and is idempotent). Do NOT touch `_PROVIDER` directly from `main.py`.
- [ ] 4.2 Wrap each finalizer in `try/except` + warn log.

## 5. Smoke tests

- [ ] 5.1 Manual: run the worker, enqueue a row that takes >1 s, SIGTERM the worker mid-handler; confirm the row commits before exit (or rolls back cleanly if still in flight).
- [ ] 5.2 Manual: run the API under uvicorn, hit a slow endpoint, SIGTERM, confirm the in-flight request completes before the process exits and `/health/ready` returns 503 while draining.

## 6. Wrap-up

- [ ] 6.1 `make ci` green.
