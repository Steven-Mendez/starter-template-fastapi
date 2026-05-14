## 1. Use case

- [x] 1.1 Create `src/features/outbox/application/use_cases/maintenance/__init__.py`.
- [x] 1.2 Create `src/features/outbox/application/use_cases/maintenance/prune_outbox.py` defining a `@dataclass(slots=True) class PruneOutbox` with `execute(retention_delivered_days: int, retention_failed_days: int, dedup_retention_seconds: float, batch_size: int) -> Result[PruneSummary, ApplicationError]`.
- [x] 1.3 Implementation loops three calls — `delete_delivered_before`, `delete_failed_before`, `delete_processed_marks_before` — each in its own transaction, batching at `batch_size`, until the matching set is empty.
- [x] 1.4 `PruneSummary` reports per-table counts deleted; logged at INFO.

## 2. Repository

- [x] 2.1 In `src/features/outbox/adapters/outbound/sqlmodel/repository.py`, add:
  - `delete_delivered_before(cutoff: datetime, limit: int) -> int` (returns rows deleted).
  - `delete_failed_before(cutoff: datetime, limit: int) -> int`.
  - `delete_processed_marks_before(cutoff: datetime, limit: int) -> int`.
- [x] 2.2 Each uses `DELETE FROM ... WHERE id IN (SELECT id FROM ... WHERE ... LIMIT :limit)` to bound transaction size.

## 3. Settings

- [x] 3.1 In `src/features/outbox/composition/settings.py:31`, add `retention_delivered_days: int = 7` to `OutboxSettings` and wire `from_app_settings` (line 41) to read `app.outbox_retention_delivered_days` (env `APP_OUTBOX_RETENTION_DELIVERED_DAYS`).
- [x] 3.1a In the same file, add `retention_failed_days: int = 30` and wire `from_app_settings` to read `app.outbox_retention_failed_days` (env `APP_OUTBOX_RETENTION_FAILED_DAYS`).
- [x] 3.1b In the same file, add `prune_batch_size: int = 1000` and wire `from_app_settings` to read `app.outbox_prune_batch_size` (env `APP_OUTBOX_PRUNE_BATCH_SIZE`).
- [x] 3.2 Extend the existing `validate(errors)` method (`src/features/outbox/composition/settings.py:71`) to require all three new fields are positive; emit a warning (not a hard error) when `retention_failed_days < retention_delivered_days`.
- [x] 3.3 In the same module, expose a derived `dedup_retention_seconds = 2 * retry_max_seconds` (read from the field landed by `fix-outbox-dispatch-idempotency`) so `PruneOutbox` does not need a second knob.

## 4. Worker cron

- [x] 4.1 In `src/worker.py`, register an arq cron via `arq.cron.cron(coroutine=..., minute={0})` (fires hourly on the hour) that invokes `PruneOutbox.execute(...)` with the settings projection. Register inside the same `cron_jobs: list[CronJob]` block as the relay cron — never in `src/main.py` (the web process must not run the prune).
- [x] 4.2 Only schedule the cron when `APP_OUTBOX_ENABLED=true` (mirrors the relay registration). When disabled, leave the cron list untouched.
- [x] 4.3 Add a `# .PHONY` entry in `Makefile` for the new `outbox-prune` target (sibling changes — `speed-up-ci` — already track the same omission for `outbox-retry-failed`).

## 5. CLI + Makefile

- [x] 5.1 Create `src/cli/outbox_prune.py` — a `python -m` entrypoint that builds the composition root, runs `PruneOutbox.execute(...)` once, prints the summary, exits.
- [x] 5.2 Add `outbox-prune` to `Makefile` invoking `uv run python -m src.cli.outbox_prune`.

## 6. Tests

- [x] 6.1 Integration (Postgres): seed 1000 `delivered` rows split across `delivered_at = now() - 10d` and `delivered_at = now() - 1d`; 200 `failed` rows split across `failed_at = now() - 40d` and `failed_at = now() - 1d`; 500 `processed_outbox_messages` rows split across `processed_at` ages. Run `PruneOutbox.execute(retention_delivered_days=7, retention_failed_days=30, dedup_retention_seconds=2*900, batch_size=100)`. Assert: old rows deleted, recent rows survive.
- [x] 6.2 Integration: batch boundary — seed `batch_size + 50` eligible rows; assert all are deleted across multiple internal iterations.
- [x] 6.3 Unit: `PruneSummary` reports correct counts.
- [x] 6.4 Unit (settings): validator rejects negative retention values; warns on `retention_failed_days < retention_delivered_days`.

## 7. Docs

- [x] 7.1 Update `docs/outbox.md` with a retention section: defaults, env vars, cron cadence, batch sizing, dedup-table retention rationale.
- [x] 7.2 Update `docs/operations.md` env-var table.

## 8. Wrap-up

- [x] 8.1 `make ci` green.
- [x] 8.2 Manually exercise: `make outbox-prune` on a dev DB after backdating some rows.
