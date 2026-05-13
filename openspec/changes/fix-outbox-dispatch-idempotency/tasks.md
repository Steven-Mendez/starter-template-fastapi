## 1. Per-row dispatch transaction

- [ ] 1.1 In `src/features/outbox/application/use_cases/dispatch_pending.py`, restructure the inner loop of `execute()` (lines 81-113) so each iteration opens its own transaction-scoped writer, enqueues to the job queue inside it, marks the row `delivered`, and commits before moving to the next row.
- [ ] 1.2 In the same file, remove the trailing batch call `if dispatched_ids: self._repository.mark_dispatched(...)` (lines 116-117) and the `dispatched_ids` accumulator (line 78); each row is now marked inline.
- [ ] 1.3 Keep `FOR UPDATE SKIP LOCKED` on the claim query in `src/features/outbox/adapters/outbound/sqlmodel/repository.py` (line 76) so concurrent relay workers do not contend.
- [ ] 1.4 Inject the row's `OutboxMessage.id` into the enqueued payload under the reserved key `__outbox_message_id`. Build the dispatched payload as `{**row.payload, "__outbox_message_id": str(row.id)}` so any reserved key the producer already wrote (e.g. `__trace` from a sibling change) is preserved verbatim — never overwrite an existing `__*` key the row already carries.
- [ ] 1.5 (Forward-compat) The relay MUST NOT strip unknown `__*` keys from `row.payload` when constructing the dispatched payload. This is what lets sibling changes (`propagate-trace-context-through-jobs`) add reserved keys without coordinating a relay change.

## 2. Row-state machine rename

- [ ] 2.1 In `src/features/outbox/domain/status.py`, change `OutboxStatus = Literal["pending", "dispatched", "failed"]` to `Literal["pending", "delivered", "failed"]`.
- [ ] 2.2 In `src/features/outbox/domain/message.py`, rename the field `dispatched_at: datetime | None` → `delivered_at: datetime | None`.
- [ ] 2.3 In `src/features/outbox/adapters/outbound/sqlmodel/models.py`, rename the column `dispatched_at` → `delivered_at` (line 93).
- [ ] 2.3a Update the docstrings in the same file (lines 6, 29, and 32) referencing `dispatched` to use `delivered`.
- [ ] 2.3b Update the row-coercion validator in `src/features/outbox/adapters/outbound/sqlmodel/repository.py:174-177` (`_coerce_status`) to accept `"delivered"` instead of `"dispatched"`.
- [ ] 2.4 Rename the port method `OutboxRepositoryPort.mark_dispatched` → `mark_delivered` (`src/features/outbox/application/ports/outbound/outbox_repository_port.py:48`) and the timestamp keyword `dispatched_at=` → `delivered_at=`. Update the SQLModel adapter implementation (`repository.py:111`).
- [ ] 2.5 Update every test file under `src/features/outbox/tests/` that references `dispatched`, `mark_dispatched`, `dispatched_at`, or asserts `status == "dispatched"`. Verified hits: `tests/unit/test_dispatch_pending.py`, `tests/integration/test_relay_dispatch.py`, `tests/fakes/fake_outbox.py`. Sweep with `rg dispatched src/features/outbox/tests/`.
- [ ] 2.6 Alembic Revision A (transactional): `UPDATE outbox_messages SET status='delivered' WHERE status='dispatched'; ALTER TABLE outbox_messages RENAME COLUMN dispatched_at TO delivered_at;`. Note: `status` is a free-text `String(length=16)` column, not a Postgres ENUM — no enum drop/create needed.

## 3. Handler idempotency contract

- [ ] 3.1 Update `OutboxPort.enqueue(...)` docstring in `src/features/outbox/application/ports/outbox_port.py` to state that the relay injects `__outbox_message_id` into the payload before delivering to the job queue, and that handlers MUST be idempotent on it.
- [ ] 3.2 In Revision A above, also `CREATE TABLE processed_outbox_messages (id UUID PRIMARY KEY, processed_at TIMESTAMPTZ NOT NULL DEFAULT now())`. Declare a matching SQLModel in `src/features/outbox/adapters/outbound/sqlmodel/models.py`.
- [ ] 3.3 Update the `send_email` handler in `src/features/email/composition/jobs.py` to be a no-op if it has already processed the given `__outbox_message_id` (insert into `processed_outbox_messages` inside the handler's transaction; treat duplicate-PK as `Ok`).

## 4. Exponential backoff

- [ ] 4.1 Add `retry_base_seconds: float` and `retry_max_seconds: float` fields to `OutboxSettings` in `src/features/outbox/composition/settings.py`, defaults `30.0` and `900.0`. Wire them through `from_app_settings(...)` (line 41) reading new attributes `app.outbox_retry_base_seconds` / `app.outbox_retry_max_seconds` from `AppSettings` (env vars `APP_OUTBOX_RETRY_BASE_SECONDS` / `APP_OUTBOX_RETRY_MAX_SECONDS`). Extend the existing `validate(errors)` method (line 71) to require both > 0 and `retry_max >= retry_base`.
- [ ] 4.2 In `src/features/outbox/application/use_cases/dispatch_pending.py`, drop the module-level `_RETRY_DELAY = timedelta(seconds=30)` (line 44).
- [ ] 4.2a In the same file, replace the dataclass field `_retry_delay: timedelta = _RETRY_DELAY` (line 66) with `_retry_base: timedelta` and `_retry_max: timedelta` (no defaults — passed by `composition/container.py`).
- [ ] 4.2b In the same file, on retry compute `delay = min(self._retry_base * (2 ** (next_attempts - 1)), self._retry_max)` and use `available_at = now + delay` (replaces line 104 `available_at=now + self._retry_delay`).
- [ ] 4.2c Update the module docstring (lines 40-44) — the rationale defending the fixed delay is no longer accurate.
- [ ] 4.3 In `src/features/outbox/composition/container.py:69-75`, pass the two new settings to `DispatchPending(...)`.

## 5. Index tiebreaker

- [ ] 5.1 Alembic Revision B (separate file from Revision A in section 2.6 — `CREATE INDEX CONCURRENTLY` cannot run inside a transactional migration): drop `ix_outbox_pending` and recreate it on `(available_at, id) WHERE status='pending'` using `op.execute("DROP INDEX CONCURRENTLY ix_outbox_pending")` and `op.execute("CREATE INDEX CONCURRENTLY ix_outbox_pending ...")` inside `with op.get_context().autocommit_block():`.
- [ ] 5.2 Update `src/features/outbox/adapters/outbound/sqlmodel/models.py` `__table_args__` (lines 38-45) to declare the new index shape `sa.Index("ix_outbox_pending", "available_at", "id", postgresql_where=sa.text("status = 'pending'"))` (for `--autogenerate` consistency).
- [ ] 5.3 Update the claim query in `src/features/outbox/adapters/outbound/sqlmodel/repository.py` to `ORDER BY available_at, id` (was `ORDER BY available_at` only) so the planner uses the new index.

## 6. Repository cleanup

- [ ] 6.1 In `src/features/outbox/adapters/outbound/sqlmodel/repository.py`, replace `cast(Any, OutboxMessageTable.id == id)` at lines 143 and 163 with `OutboxMessageTable.id == id` directly. If `mypy` still complains under `[strict]`, prefer `sa.update(OutboxMessageTable).where(OutboxMessageTable.id == id)` typed via the `ColumnElement[bool]` returned by `==` on a SQLAlchemy column. Drop the now-unused `cast` and `Any` imports if no other call site uses them.

## 7. Tests

- [ ] 7.1 Unit (fake adapters): inject a failure on `JobQueuePort.enqueue` for one specific row → assert that row's `status` is still `pending` and `attempts` was incremented; assert the surrounding rows were marked `delivered`.
- [ ] 7.2 Unit: re-run `dispatch_pending` on a row whose `status` is already `delivered` → assert no enqueue happens (claim query excludes it).
- [ ] 7.3 Integration (Postgres + fakeredis): tick the relay twice with a row that fails on the first enqueue and succeeds on the second; assert exactly one successful enqueue and exponential backoff between attempts.
- [ ] 7.4 Integration (Postgres): assert the new index exists with the expected definition via `pg_indexes`.
- [ ] 7.5 Unit: handler receives the same `__outbox_message_id` twice → second invocation is a no-op (no duplicate email send, both invocations return `Ok`).
- [ ] 7.6 Unit: handler that re-enqueues a payload preserves an unknown reserved key (e.g. `__trace`) verbatim.

## 8. Docs

- [ ] 8.1 Update `docs/outbox.md` with the at-least-once contract, the reserved-payload-key namespace (`__outbox_message_id`, plus a forward-reference note for `__trace`), the `delivered`/`failed` state machine, and the `processed_outbox_messages` dedup table.
- [ ] 8.2 Update `CLAUDE.md` outbox env-var table with `APP_OUTBOX_RETRY_BASE_SECONDS` and `APP_OUTBOX_RETRY_MAX_SECONDS`.

## 9. Wrap-up

- [ ] 9.1 `make ci` green.
- [ ] 9.2 Manually exercise: trigger a password-reset, kill the worker between Redis enqueue and DB mark (simulate via a feature-flag raise), restart, confirm exactly one email arrives.
