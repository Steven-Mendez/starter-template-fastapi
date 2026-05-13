## Context

Containers receive SIGTERM with a deadline. Done well: in-flight requests finish, the queue drains, connections close cleanly. Done poorly: requests are cut mid-response, half-claimed outbox rows hang in `processing` state, DB connections leak until the kernel reaps the socket. Today the template does the poor version — `src/main.py`'s lifespan never disposes the engine or closes Redis, and `src/worker.py:WorkerSettings` defines `on_startup` but no `on_shutdown`.

## Decisions

- **API drain budget = `APP_SHUTDOWN_TIMEOUT_SECONDS` (default 30 s)**. On SIGTERM the FastAPI lifespan stops accepting new requests (uvicorn handles the `--timeout-graceful-shutdown` flag) and drains in-flight requests up to the same budget before the finalizer disposes the engine, closes Redis, and shuts down the OTel `TracerProvider`.
- **Worker drain budget = same `APP_SHUTDOWN_TIMEOUT_SECONDS` (default 30 s)**, surfaced through `arq`'s `on_shutdown`. The worker waits for in-flight `DispatchPending.execute` ticks and active job handlers to finish, then disposes the engine and closes Redis. The legacy `APP_WORKER_SHUTDOWN_GRACE_SECONDS` knob is renamed to `APP_SHUTDOWN_TIMEOUT_SECONDS` so the API and worker share one timeout.
- **K8s budget 35 s**: the orchestrator budget is the inner-most timeout + 5 s slack, so the process gives up first and K8s sees a clean exit instead of SIGKILL.
- **Engine disposal in lifespan finalizer**: the engine outlives every request; disposing on shutdown is the only correct lifecycle hook. Each finalizer step is wrapped in `try/except` + warn log so a slow Redis does not skip `engine.dispose()`.
- **No per-request grace control**: too fiddly; uvicorn's request-level timeout is sufficient.

## Risks / Trade-offs

- **Risk**: a single hung request blocks the whole replica for 30 s. Mitigation: that's the intended behaviour; cutting the request mid-flight is worse for clients than a one-time 30 s drain on deploy.
- **Risk**: PID 1 swallows SIGTERM if no init forwarder is present. Mitigation: `harden-dockerfile` installs `tini` and sets `ENTRYPOINT ["tini", "--"]`; this change assumes that lands first.

## Depends on

- `harden-dockerfile` — provides `tini` PID-1 forwarder so SIGTERM actually reaches uvicorn / the worker.
- `add-readiness-probe` — provides the lifespan-ready flag; on shutdown the flag is cleared so `/health/ready` returns 503 while requests drain.

## Conflicts with

- `src/worker.py` is also touched by `schedule-token-cleanup`, `add-outbox-retention-prune`, `propagate-trace-context-through-jobs`, `document-arq-result-retention`, `type-cleanup-strategic-anys`, `clean-user-assets-on-deactivate` (cron-registration surface). This change adds the `on_shutdown` hook only — coordinate the merge order so cron registrations stay grouped.
- `src/main.py` lifespan is also touched by `add-readiness-probe`, `clean-architecture-seams`, `fix-bootstrap-admin-escalation`, `make-auth-flows-transactional`. The finalizer block must run after all of those have installed their cleanup hooks.
- `Dockerfile` `CMD` is also touched by `harden-dockerfile`, `add-worker-image-target`, `trim-runtime-deps`. Rebase ordering: `harden-dockerfile` → `add-worker-image-target` → this change appends `--timeout-graceful-shutdown 30` to the uvicorn `CMD` in both runtime stages.

## Migration

Single PR. Rollback: revert.
