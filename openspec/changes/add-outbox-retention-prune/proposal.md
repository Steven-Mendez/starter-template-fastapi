## Why

Once an outbox row reaches `status='delivered'` it stays in the table forever; `failed` rows also pile up unless an operator clears them manually. The partial pending-index helps the relay claim query, but full-table operations (autovacuum, backups, replicas) suffer linearly with table size. Additionally, the `processed_outbox_messages` dedup table introduced by `fix-outbox-dispatch-idempotency` has no retention plan and grows 1:1 with throughput.

## What Changes

- Add a `PruneOutbox` use case in `src/features/outbox/application/use_cases/maintenance/prune_outbox.py` that:
  - Deletes from `outbox_messages` where `status='delivered' AND delivered_at < now() - retention_delivered`.
  - Deletes from `outbox_messages` where `status='failed' AND failed_at < now() - retention_failed`.
  - Deletes from `processed_outbox_messages` where `processed_at < now() - 2 * retry_max` (the safe lower bound: by the time we might redrive a row, its dedup mark would already be older).
- Settings: `APP_OUTBOX_RETENTION_DELIVERED_DAYS` (default 7), `APP_OUTBOX_RETENTION_FAILED_DAYS` (default 30), `APP_OUTBOX_PRUNE_BATCH_SIZE` (default 1000).
- Register an arq cron on the worker that runs the prune every 1 hour.
- Expose a `make outbox-prune` target and a CLI subcommand for one-shot operator use.

## Depends on

- **fix-outbox-dispatch-idempotency** — must land first. It introduces the `delivered`/`failed` terminal states this change reads, the `delivered_at` / `failed_at` timestamp columns, the `processed_outbox_messages` dedup table, and the `retry_max` setting that bounds the dedup retention window.
- **propagate-trace-context-through-jobs** — should land before this change so the worker cron registered here is wrapped in the standard context-attach/detach scaffolding (purely operational; functional behavior is unaffected if it lands after).

## Conflicts with

- **fix-outbox-dispatch-idempotency** — co-edits `src/features/outbox/adapters/outbound/sqlmodel/repository.py` and `src/features/outbox/composition/settings.py`. Sequenced after.
- **propagate-trace-context-through-jobs** — co-edits `src/worker.py` (cron registration). Trivial merge; both changes register independent crons.

## Reserved payload keys (shared contract across the outbox cluster)

This change does not introduce any new reserved keys. The prune use case is invoked directly on a schedule and is opaque to row payloads. Documented here so every change in the cluster ships the same table:

| Key | Introduced by | Type / shape |
|---|---|---|
| `__outbox_message_id` | `fix-outbox-dispatch-idempotency` | str — `OutboxMessage.id` (UUID) |
| `__trace` | `propagate-trace-context-through-jobs` | `{"traceparent": str, "tracestate": str?}` (W3C) |

**Capabilities — Modified**: `outbox`.

## Impact

- **Code**: `src/features/outbox/application/use_cases/maintenance/prune_outbox.py` (new), `src/features/outbox/adapters/outbound/sqlmodel/repository.py` (three new methods), `src/features/outbox/composition/settings.py` (three new fields + validators), `src/worker.py` (hourly cron registration), `src/cli/outbox_prune.py` (new CLI entrypoint), `Makefile` (`outbox-prune` target).
- **Migrations**: none. Operates on tables and columns already created by `fix-outbox-dispatch-idempotency`.
- **Docs**: `docs/outbox.md` (retention section), `docs/operations.md` (env-var table).
- **Tests**: integration test seeding old `delivered` rows, old `failed` rows, old dedup rows, running prune, asserting correct deletion and that recent rows survive.
- **Production**: bounded outbox-table and dedup-table size; predictable backup/replica overhead.
