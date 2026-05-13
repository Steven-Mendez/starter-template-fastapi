## Why

`src/worker.py:129-137` sets `queue_name` and `redis_settings` on `WorkerSettings` but leaves `keep_result`, `keep_result_forever`, `max_jobs`, `job_timeout` at arq defaults. Operators have no documented Redis-prune story; on a stressed deploy `arq:queue:result:*` keys accumulate.

The current job catalog is fire-and-forget (`send_email`, `delete_user_assets`, future maintenance crons). A single sensible retention default is enough today, with a per-handler escape hatch when a future job genuinely needs longer retention.

## What Changes

- Default `keep_result_seconds = 300` (5 minutes). Rationale: long enough to correlate the Redis result with a log line and short enough that Redis memory stays bounded.
- One setting: `APP_JOBS_KEEP_RESULT_SECONDS_DEFAULT = 300`. The handler registry accepts an optional per-handler `keep_result_seconds: int | None = None` override; `WorkerSettings.keep_result` is computed per-job via arq's per-function `keep_result`.
- Set `max_jobs: int = 16` (tunable per-deployment CPU/memory).
- Set `job_timeout: int = 600` (10 min) so a hung handler doesn't pin a worker forever.
- Document the recommended Redis `maxmemory-policy allkeys-lru` and `maxmemory` sizing in `docs/background-jobs.md` and `docs/operations.md`.

**Capabilities — Modified**: `project-layout`.

## Impact

- **Code**:
  - `src/worker.py` (~6 lines of `WorkerSettings` wiring + per-function `keep_result`).
  - `src/features/background_jobs/composition/settings.py` (new `JobsSettings` field).
  - `src/features/background_jobs/application/registry.py` (extend `register` signature with `keep_result_seconds: int | None = None`).
  - `docs/background-jobs.md` (new "Redis operational guidance" section).
  - `docs/operations.md` (env-var table update).
- **Production**: bounded Redis usage for job results; configurable.

## Depends on / Conflicts with

- **Depends on**: none.
- **Conflicts with**: `src/worker.py` is shared with `add-graceful-shutdown`, `type-cleanup-strategic-anys`, `schedule-token-cleanup`, `add-outbox-retention-prune`, `propagate-trace-context-through-jobs`, `clean-user-assets-on-deactivate` — section-level edits to the same `WorkerSettings` block; coordinate at merge time.
