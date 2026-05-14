## Context

The outbox is append-write-once-marked-delivered. Without retention it monotonically grows; the dedup table introduced by `fix-outbox-dispatch-idempotency` grows 1:1 with throughput. We add the standard ops pattern: time-bounded delete via cron.

## Depends on

- **fix-outbox-dispatch-idempotency** — strict prerequisite. Provides the `delivered` / `failed` terminal states, the `delivered_at` / `failed_at` timestamp columns, the `processed_outbox_messages` dedup table, and the `retry_max_seconds` setting used to compute the dedup retention floor.
- **propagate-trace-context-through-jobs** — soft prerequisite. The hourly prune cron should run inside the worker's standard context-attach/detach scaffolding so prune operations show up as spans on the same traces as everything else; functional behavior is unaffected if it lands after.

## Conflicts with

- **fix-outbox-dispatch-idempotency** — same `src/features/outbox/adapters/outbound/sqlmodel/repository.py` + `src/features/outbox/composition/settings.py`. Sequenced after.
- **propagate-trace-context-through-jobs** — same `src/worker.py` cron-registration surface. Independent crons; trivial merge.
- **schedule-token-cleanup** — same `src/worker.py` cron-registration surface. Independent crons; trivial merge.
- **add-worker-image-target** / **speed-up-ci** — share `Makefile` `.PHONY` block; section-level edits only.

## Reserved payload keys (cluster-wide contract)

Identical to every change in the cluster. Prune does not introduce new keys and treats existing ones as opaque.

| Key | Introduced by | Type / shape |
|---|---|---|
| `__outbox_message_id` | `fix-outbox-dispatch-idempotency` | str — `OutboxMessage.id` (UUID) |
| `__trace` | `propagate-trace-context-through-jobs` | `{"traceparent": str, "tracestate": str?}` (W3C) |

## Non-goals

- A dead-letter-redrive UI or admin endpoint. `failed` rows are kept on disk for the retention window; investigating them is operator-tooling work outside this change.
- Archival of pruned rows to cold storage (S3 etc.). Pruned rows are deleted, not moved.
- Per-job-name retention overrides. A single pair of retention knobs applies to every row.
- Automatic alerting when pruned-row counts spike. Counts are logged at INFO; alerting is operator-config work.
- Compaction of `outbox_messages` after large prunes (autovacuum is sufficient).

## Decisions

### Decision 1: Different retention for `delivered` vs `failed`

- **Chosen**: `delivered` rows are best-effort audit trail and are pruned aggressively (default 7 days). `failed` rows are operator-actionable evidence of dead-lettered work and are kept longer (default 30 days).
- **Rejected**: a single retention. Cheaper to implement, but conflates two operationally different signals.

### Decision 2: Dedup-table retention pegged to `2 × retry_max`

- **Chosen**: `processed_outbox_messages` rows older than `2 × APP_OUTBOX_RETRY_MAX_SECONDS` are eligible for deletion. By the time the relay would re-attempt a row that old (it can't — the row is either `delivered` or `failed` by then), the dedup mark is moot.
- **Rationale**: avoids exposing a separate knob for an internal correctness boundary; the dedup retention follows the retry budget automatically.

### Decision 3: Cron cadence — hourly

- **Chosen**: arq cron registered on the worker, fires every 1 hour on the hour. Frequent enough that table size stays bounded near the retention window; infrequent enough that the per-prune overhead is negligible.
- **Rejected**: daily. Lets a hot system grow by a day's worth of rows between prunes; not catastrophic but louder operationally.

### Decision 4: Bounded batch size, looped per cron tick

- **Chosen**: each `DELETE ... WHERE ... AND id IN (SELECT id ... LIMIT :batch)` deletes at most `APP_OUTBOX_PRUNE_BATCH_SIZE` rows (default 1000), then loops until the matching set is empty or the cron tick's wall-clock budget is consumed.
- **Rationale**: a single unbounded `DELETE` on a large backlog can hold a long transaction and stall replicas. Batching keeps each transaction small and friendly to autovacuum.

### Decision 5: CLI subcommand for one-shot operator use

- **Chosen**: `src/cli/outbox_prune.py` invokes the same `PruneOutbox` use case as the cron. Exposed via `make outbox-prune`.
- **Rationale**: operator-facing path is the same code as the scheduled path — no skew.

## Risks / Trade-offs

- **Risk**: an operator wants to investigate a delivered row past retention. Mitigation: settings are configurable; archival to a cold table is a follow-up if needed.
- **Risk**: the hourly cron + relay both write to the same table; lock contention on the same rows? Mitigation: prune touches only `delivered` / `failed` rows; the relay only claims `pending` rows. Disjoint sets.

## Migration Plan

Single PR, sequenced after `fix-outbox-dispatch-idempotency`. No schema migrations (all tables/columns already exist by then). Rollback: revert the code; no data is recreated, only deleted, so rollback can't restore pruned rows — but the only thing pruned is data already past its operational lifetime.
