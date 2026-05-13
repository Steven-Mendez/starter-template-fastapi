## Context

Most `Any` in this codebase is glue (e.g. arq `ctx: dict[str, Any]` — legitimate). A handful are not: they exist to suppress a typing complaint about an under-declared type. We fix the under-declaration.

## Decisions

- **`Protocol` over concrete class** for `UserSnapshot`: duck-typed against whatever `UserPort.get_by_id` returns; a Protocol is the minimal interface.
- **Declare `WorkerSettings` attributes** with their real arq types (`Function`, `CronJob`, `RedisSettings`). Drop the `Any` cast at the `arq.run_worker(WorkerSettings)` call site.
- **Replace `Sequence[Any]` with `Sequence[CronJob]`** in `outbox/composition/worker.py:build_relay_cron_jobs(...)`. Drop the unused `app: Any = None` params elsewhere.

## Non-goals

- **Not enforcing strict mypy on `tests/`.** Test code keeps its current relaxed config; the gate from `enable-strict-mypy` applies to `src/` only.
- **Not eliminating every `Any` in the tree.** Legitimate glue points (arq `ctx: dict[str, Any]`, dynamic settings overlays, third-party stubs) stay as `Any`; this change targets only the named hotspots.
- **Not introducing a `typing.Protocol` taxonomy for every cross-feature DTO.** `UserSnapshot` is added because it removes 5 ignores in one call site; broader protocol-ification is out of scope.
- **Not upgrading the arq dependency** to gain better type stubs. We work with whatever shape the currently-pinned arq exports.

## Risks / Trade-offs

- Declaring `WorkerSettings` attributes locks us to a specific arq shape. Mitigation: arq's `WorkerSettings` is stable; if it churns, Renovate forces a coordinated bump.

## Migration

Single PR. Rollback: revert.

## Depends on

- **`enable-strict-mypy`** — lands first. Rationale: under non-strict mypy these `# type: ignore` lines and `Any` slips are not flagged; "cleaning them up" without the gate just trades one form of debt for another. Strict mode is what makes this work durable.

## Conflicts with

- Shares `src/worker.py` with `add-graceful-shutdown`, `document-arq-result-retention`, `schedule-token-cleanup`, `add-outbox-retention-prune`, `propagate-trace-context-through-jobs`.
- Shares `src/features/outbox/composition/settings.py` with `fix-outbox-dispatch-idempotency`, `add-outbox-retention-prune`.
- Shares `src/features/background_jobs/composition/settings.py` with `document-arq-result-retention`.

Coordinate landing order so the typed `WorkerSettings` shape is in place before other worker-touching changes add new attributes (otherwise each addition needs its own annotation tweak).
