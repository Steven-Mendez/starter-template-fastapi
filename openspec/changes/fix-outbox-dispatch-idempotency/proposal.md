## Why

The outbox relay was introduced to make cross-feature side effects atomic with the business write. It almost succeeds, but the dispatch loop itself has a duplicate-delivery race:

`src/features/outbox/application/use_cases/dispatch_pending.py:81-117` claims a batch of pending rows, calls `JobQueuePort.enqueue(...)` for each one inside the claim transaction, then commits and opens a **separate** transaction to mark each row's terminal-success state. If the worker crashes (or its Postgres connection drops) between the Redis enqueue and the terminal-state mark, the rows stay `pending`; the next relay tick re-claims them and enqueues the same job again. The `send_email` handler is not idempotent on the receiving side, so users get duplicate password-reset and verification emails.

Three smaller defects compound the issue:

1. Constant 30-second retry (`_RETRY_DELAY`, `dispatch_pending.py:44`) means a poison handler burns the entire `max_attempts=8` budget in four minutes, re-enqueuing to Redis in lockstep and amplifying load downstream. The current docstring defends this as "one knob too many for a starter pattern", but the failure mode it produces (lockstep re-enqueue under load) makes that wrong: jitter and backoff are exactly the controls a starter pattern needs.
2. The partial index `ix_outbox_pending` is on `(available_at)` alone with no `id` tiebreaker (`adapters/outbound/sqlmodel/models.py:38-45`). Under heavy lock contention the `ORDER BY available_at LIMIT N FOR UPDATE SKIP LOCKED` scan order is undefined and SKIP LOCKED can spin.
3. `mark_retry` and `mark_failed` build their `WHERE` clauses with `cast(Any, OutboxMessageTable.id == id)` (`repository.py:143, 163`). It happens to produce the right SQL today, but is one refactor away from a silent table-wide UPDATE — `cast(Any, …)` strips the type-checker's ability to catch a slip from `==` to `is`.

## What Changes

- Refactor the dispatch loop to one transaction per row: claim → enqueue → mark terminal state, all in the same transaction. A crash before the mark MUST leave the row visible to be re-claimed; a crash *after* the enqueue but before the commit is fine because the row is still `pending`. To make the resulting at-least-once delivery safe, the enqueued payload now carries `__outbox_message_id` and handlers MUST be idempotent on it (documented contract; `send_email` updated accordingly).
- Lock in the outbox row-state machine: `pending → delivered` on successful enqueue + commit; `pending → failed` once `attempts ≥ max_attempts`. (Renames the previous `dispatched` terminal state to `delivered` for clarity and to match the prune/retention vocabulary.)
- Replace constant `_RETRY_DELAY` with exponential backoff: `available_at = now + min(retry_base * 2 ** (attempts - 1), retry_max)`. Settings: `APP_OUTBOX_RETRY_BASE_SECONDS=30`, `APP_OUTBOX_RETRY_MAX_SECONDS=900`.
- Add `(available_at, id)` to the partial index so the claim ORDER BY is fully ordered.
- Replace `cast(Any, OutboxMessageTable.id == id)` with `OutboxMessageTable.id == id` directly (typed correctly via SQLAlchemy ColumnElement). Same for `mark_failed`.
- Reserve the `__*` payload-key prefix for relay metadata. This change introduces `__outbox_message_id`; sibling changes layer more reserved keys on top (see "Depends on" / "Conflicts with"). Handlers MUST preserve unknown reserved keys when re-enqueuing on retry.

## Depends on

- None upstream. This change lays the row-state machine and the reserved-payload-key contract every sibling outbox change builds on.

## Conflicts with

- **propagate-trace-context-through-jobs** — co-edits `src/features/outbox/application/use_cases/dispatch_pending.py` and `src/features/outbox/adapters/outbound/sqlmodel/models.py`. Land this change first; trace-context adds the `__trace` reserved payload key and the `trace_context` column on top of the state machine here.
- **add-outbox-retention-prune** — depends on the `delivered`/`failed` terminal states and the `processed_outbox_messages` dedup table introduced here.

## Reserved payload keys (shared contract across the outbox cluster)

The relay reserves the `__*` namespace inside the job payload. Non-reserved keys are the original handler payload, untouched. Handlers MUST preserve unknown reserved keys when re-enqueuing on retry (so that future sibling changes can add keys without breaking older handlers).

| Key | Introduced by | Value |
|---|---|---|
| `__outbox_message_id` | this change | UUID string — `OutboxMessage.id`, used by handlers to deduplicate |
| `__trace` | `propagate-trace-context-through-jobs` | dict with `traceparent` (W3C string) and optional `tracestate` |

**Capabilities — Modified**
- `outbox`: tightens dispatch and ordering requirements; defines the row-state machine (`pending → delivered | failed`) and the reserved-payload-key namespace.

**Capabilities — New**
- None.

## Impact

- **Code**:
  - `src/features/outbox/application/use_cases/dispatch_pending.py` — per-row transaction, exponential backoff, payload key injection.
  - `src/features/outbox/adapters/outbound/sqlmodel/repository.py` — implements per-row mark inside the claim transaction; renames `mark_dispatched` → `mark_delivered`; drops `cast(Any, ...)` in `mark_retry` / `mark_failed`.
  - `src/features/outbox/adapters/outbound/sqlmodel/models.py` — column rename `dispatched_at` → `delivered_at`; new partial-index shape.
  - `src/features/outbox/domain/message.py` — `dispatched_at` field renamed on the domain entity.
  - `src/features/outbox/domain/status.py` — `OutboxStatus = Literal["pending", "delivered", "failed"]` (was `["pending", "dispatched", "failed"]`).
  - `src/features/outbox/application/ports/outbound/outbox_repository_port.py` — port method `mark_dispatched` → `mark_delivered`.
  - `src/features/outbox/composition/settings.py` — add `retry_base_seconds` / `retry_max_seconds` (no existing `relay_retry_seconds` to remove — current default is hard-coded as `_RETRY_DELAY` in the use case).
  - `src/features/outbox/composition/container.py` — pass new settings to `DispatchPending`.
  - `src/features/email/composition/jobs.py` — handler idempotency on `__outbox_message_id`.
  - All outbox tests under `src/features/outbox/tests/` reference `dispatched`/`mark_dispatched` and need the rename swept.
- **Migrations** (two separate Alembic revisions because `CREATE INDEX CONCURRENTLY` cannot run inside a transactional migration):
  - Revision A (transactional): `UPDATE outbox_messages SET status='delivered' WHERE status='dispatched'`; `ALTER TABLE outbox_messages RENAME COLUMN dispatched_at TO delivered_at`; `CREATE TABLE processed_outbox_messages (id UUID PRIMARY KEY, processed_at TIMESTAMPTZ NOT NULL DEFAULT now())`. (`status` is a free-text `String(length=16)` column, not a Postgres ENUM — the migration is plain SQL.)
  - Revision B (autocommit block): `DROP INDEX CONCURRENTLY ix_outbox_pending; CREATE INDEX CONCURRENTLY ix_outbox_pending ON outbox_messages (available_at, id) WHERE status='pending'`.
- **Docs**: `docs/outbox.md`, `CLAUDE.md` (env-var table additions).
- **Production**: a deploy that lags between relay enqueue and DB mark will now self-heal cleanly; before, it produced duplicate emails.
- **Tests**: re-tick on already-delivered row → no double enqueue; injected failure between enqueue and mark → row stays `pending` and re-dispatched once; exponential-backoff progression assertion; index-presence assertion via `pg_indexes`; handler dedup assertion via `processed_outbox_messages`.
