## 1. Settings

- [x] 1.1 Add to `JobsSettings` (`src/features/background_jobs/composition/settings.py`):
  - `keep_result_seconds_default: int = 300` (env: `APP_JOBS_KEEP_RESULT_SECONDS_DEFAULT`).
  - `max_jobs: int = 16` (env: `APP_JOBS_MAX_JOBS`).
  - `job_timeout_seconds: int = 600` (env: `APP_JOBS_JOB_TIMEOUT_SECONDS`).

## 2. Registry support

- [x] 2.1 Extend `JobHandlerRegistry.register(name, handler, *, keep_result_seconds: int | None = None)` in `src/features/background_jobs/application/registry.py`.
- [x] 2.2 Persist the per-handler `keep_result_seconds` on the registry entry so the arq adapter can read it at worker boot.

## 3. WorkerSettings

- [x] 3.1 In `src/worker.py` (around the `WorkerSettings` class at lines 129-137), assign `WorkerSettings.max_jobs` from `jobs_settings.max_jobs`.
- [x] 3.2 In the same `WorkerSettings` block, assign `WorkerSettings.job_timeout` from `jobs_settings.job_timeout_seconds`.
- [x] 3.3 Per-function `keep_result`: in `features/background_jobs/adapters/outbound/arq/build_arq_functions`, set `keep_result = entry.keep_result_seconds if entry.keep_result_seconds is not None else keep_result_seconds_default` on each constructed `Function`.

## 4. Docs

- [x] 4.1 Add a "Redis operational guidance" section to `docs/background-jobs.md` covering:
  - The 300s default rationale and how to override globally via env var.
  - `maxmemory-policy allkeys-lru` and `maxmemory` sizing.
  - Checklist: "When you register a job whose result must outlive a long client-replay window (e.g., a payment idempotency key), pass `keep_result_seconds=<window-seconds>`".
- [x] 4.2 Update the env-var table in `docs/operations.md` with the three new variables.

## 5. Tests

- [x] 5.1 Unit: `WorkerSettings`-construction reflects the configured `max_jobs` and `job_timeout`.
- [x] 5.2 Unit: a handler registered with an explicit `keep_result_seconds=N` is materialized into an arq `Function` whose `keep_result == N`.
- [x] 5.3 Unit: a handler registered without `keep_result_seconds` produces a `Function` whose `keep_result == keep_result_seconds_default`.

## 6. Wrap-up

- [x] 6.1 `make ci` green.
