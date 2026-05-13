## Context

arq's defaults are sensible for getting started; they're not what you want for a long-running production deployment. Without an explicit `keep_result`, result keys accumulate in Redis under any sustained throughput. A single sensible default is enough for the current job catalog (all fire-and-forget today: `send_email`, `delete_user_assets`, future maintenance crons).

## Decisions

- **Single default**: `keep_result_seconds = 300` (5 min). Rationale: long enough to correlate the Redis result with the log entry that produced it; short enough that Redis memory stays bounded under load.
- **Per-handler override available.** The `JobHandlerRegistry.register` signature gains an optional `keep_result_seconds: int | None = None` so a future handler that genuinely needs longer retention (e.g., a billing job an external client polls) can opt in without changing the platform default. arq supports per-function `keep_result` via the `keep_result` attribute on `Function`, which the registry sets.
- **Configurable**: `APP_JOBS_KEEP_RESULT_SECONDS_DEFAULT` overrides the platform default.
- **Other knobs**:
  - `max_jobs = 16` — tunable per CPU/memory budget. The default is conservative and assumes ~1 vCPU.
  - `job_timeout = 600` (10 min) — a hung handler must not pin a worker forever.
- **`maxmemory-policy allkeys-lru` recommendation, not enforcement**: a Redis-side choice, beyond our deploy boundary.

## Risks / Trade-offs

- **Risk**: Shorter retention loses debugging signal. Mitigation: configurable globally and per-handler.
- **Risk**: A future handler reachable from a long-replay-window flow (e.g., a payment idempotency key) needs longer retention and is registered without the override. Mitigation: documented checklist in `docs/background-jobs.md`; the per-handler override is the documented escape hatch.

## Migration

Single PR. Backwards compatible — existing handlers pick up the 300s default.
