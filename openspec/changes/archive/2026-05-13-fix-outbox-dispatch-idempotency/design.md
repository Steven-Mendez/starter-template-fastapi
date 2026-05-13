## Context

The outbox pattern provides at-least-once delivery by construction: business state and "intent to do a side effect" land in the same transaction; a relay later moves the intent to the side-effect channel. The current relay batches its dispatches and commits the terminal-state mark separately from the actual enqueue. That gap is small in practice but produces duplicates whenever it does fail, and `send_email` is a user-visible side effect — duplicates show up immediately in inboxes.

## Depends on

- None upstream. This change is the foundation of the outbox cluster — it defines the row-state machine and the reserved-payload-key namespace every sibling change extends.

## Conflicts with

- **propagate-trace-context-through-jobs** — same `dispatch_pending.py` + `outbox/models.py`. Sequenced after this change; adds the `trace_context` column and the `__trace` reserved payload key on top of the state machine landed here.
- **add-outbox-retention-prune** — depends on the `delivered`/`failed` terminal states and `processed_outbox_messages` table introduced here. Sequenced after both this change and `propagate-trace-context-through-jobs`.

## Reserved payload keys (cluster-wide contract)

The relay owns the `__*` prefix inside each job payload; everything else is the handler's original payload, untouched. Handlers MUST round-trip unknown reserved keys when re-enqueuing on retry (so a new key landed by a sibling change does not get dropped by an older handler).

| Key | Introduced by | Type / shape |
|---|---|---|
| `__outbox_message_id` | this change | str — `OutboxMessage.id` (UUID); handlers dedup on it |
| `__trace` | `propagate-trace-context-through-jobs` | `{"traceparent": str, "tracestate": str?}` (W3C) |

## Goals / Non-Goals

**Goals**
- Make the relay genuinely at-least-once with handler-side deduplication. Exactly-once is not achievable across two unrelated transports (Postgres + Redis); the right correctness goal is "at-least-once + idempotent handlers".
- Establish a documented, machine-enforceable contract: every outbox handler MUST be idempotent on `__outbox_message_id`.
- Stop a single poison handler from saturating the queue via constant-cadence retries.
- Lock in the row-state machine `pending → delivered | failed` so retention/prune (and any future tooling) has a stable vocabulary.

**Non-Goals**
- Switching to a different transport that gives genuine exactly-once (Kafka transactions, FoundationDB, etc.). Outside the scope of a starter template.
- Cross-aggregate ordering. The outbox today does not promise per-aggregate FIFO; this proposal does not change that.

## Decisions

### Decision 1: Per-row transaction, not per-batch

- **Chosen**: each row claim + enqueue + terminal-state mark runs in its own transaction. The blast radius of a crash is at most one re-delivered row, instead of a whole batch.
- **Rejected**: keep the batch shape and add a "post-enqueue checkpoint" file. Cross-process state, fiddly to test, and the perf cost of per-row commits is dwarfed by the Redis round trip we're already paying.

### Decision 2: At-least-once + dedup table on the handler side

- **Chosen**: the relay injects `__outbox_message_id` into the payload; handlers write to a small `processed_outbox_messages` table inside their own transaction, treating a duplicate-PK insert as "already done, return Ok".
- **Rejected**: a "pre-commit" pattern where the handler writes the dedup row first and ROLLBACK-equivalent on send-failure. Adds DB round trips and doesn't help with non-transactional sinks (Resend, SES) where a partial send can still happen.
- **Rejected**: relying on the destination's natural idempotency (e.g. Resend `idempotency_key`). Some destinations have it, some don't; pushing the dedup into our own DB makes the contract uniform across adapters.

### Decision 3: Exponential backoff, capped

- **Chosen**: `min(base * 2^(attempts-1), max)`. Cap at 15 minutes by default to bound the longest blackout from a poison row.
- **Rejected**: jittered backoff. Worthwhile when many workers retry the *same* downstream concurrently; not the case here (one worker per row, claim is mutually exclusive).

### Decision 4: Index `(available_at, id)` with the same partial predicate

- **Chosen**: keep the partial-index optimization (`WHERE status='pending'` keeps the index small), add `id` as a tiebreaker. SKIP LOCKED needs a deterministic order to make progress on hot data.

### Decision 5: Terminal-success status named `delivered` (not `dispatched`)

- **Chosen**: rename the terminal-success state to `delivered`. The previous name `dispatched` blurs "we sent it to Redis" with "the side effect happened". `delivered` reads as "we did our part of the at-least-once contract"; `failed` is the dead-letter state once `attempts ≥ max_attempts`. The migration here flips the enum value and back-fills existing rows.
- **Rationale**: prune retention (sibling change) reads `delivered_at` / `failed_at`; a single vocabulary across the cluster avoids translation layers.

### Decision 6: Handlers MUST preserve unknown reserved keys on retry

- **Chosen**: if a handler ever re-enqueues a payload (manual replay, dead-letter-redrive tooling), it MUST keep every `__*` key it received. This lets sibling changes add reserved keys (e.g. `__trace`) without breaking older deployments.
- **Rejected**: have the relay re-inject all reserved keys on re-claim. Works for keys the relay knows about, but not for forward-compat with keys older relays don't know exist.

## Risks / Trade-offs

- **Risk**: per-row commits multiply the DB transaction count. Mitigation: outbox throughput is bounded by claim-batch size × interval anyway; we're at most going from 1 commit per N rows to N commits per N rows. With default `claim_batch_size=100` and 5-second cadence that's 20 commits/sec — trivial.
- **Risk**: the handler-side dedup table grows unboundedly. Mitigation: `add-outbox-retention-prune` (sequenced after this change) trims `processed_outbox_messages` on a cron.
- **Trade-off**: handlers gain a new responsibility (idempotency on message id). Acceptable — `send_email` is the only handler in tree, and adding dedup to it is ~15 lines.

## Migration Plan

Single PR. Migrations:

1. Add the new index migration (separate file, `CONCURRENTLY`, autocommit block).
2. Rename the `dispatched` status enum value to `delivered` (and back-fill existing rows in the same migration).
3. Create the `processed_outbox_messages` dedup table.
4. Code changes in dispatch + repository + send_email handler.

Backwards compatibility: payload key `__outbox_message_id` is additive; legacy handlers that ignore it continue to work (just without dedup). The existing payload contract is unchanged for non-outbox `JobQueuePort.enqueue` callers.

Rollback: revert the code + the migrations. `DROP INDEX CONCURRENTLY` is safe; the enum-rename migration's downgrade flips the label back.
