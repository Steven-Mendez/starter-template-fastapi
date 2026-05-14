## 1. Schema

- [x] 1.1 Add an Alembic migration: `ALTER TABLE outbox_messages ADD COLUMN trace_context JSONB NOT NULL DEFAULT '{}'::jsonb`. (Postgres 11+ stores a constant `DEFAULT` in `pg_attribute` without rewriting the table, so this is a fast metadata-only operation even on a populated table.) Per `document-one-way-migration-policy`, this is an additive migration; `downgrade()` can simply `op.drop_column("outbox_messages", "trace_context")` — no `NotImplementedError` needed.
- [x] 1.2 Declare the column on `OutboxMessageTable` in `src/features/outbox/adapters/outbound/sqlmodel/models.py` (post-`fix-outbox-dispatch-idempotency` line numbers).

## 2. Inject at enqueue

- [x] 2.1 In `SessionSQLModelOutboxAdapter.enqueue` (`src/features/outbox/adapters/outbound/sqlmodel/adapter.py:34`), capture the active OTel context: `carrier: dict[str, str] = {}; TraceContextTextMapPropagator().inject(carrier)`. Persist `carrier` into the new `trace_context` column.
- [x] 2.2 Add a small helper `propagator_inject_current()` in `src/app_platform/observability/tracing.py` so the same logic is reusable for non-outbox `JobQueuePort.enqueue` callers.

## 3. Carry through to handler

- [x] 3.1 In `DispatchPending.execute` (`src/features/outbox/application/use_cases/dispatch_pending.py`), copy `row.trace_context` into the payload under the reserved key `__trace` before calling `JobQueuePort.enqueue(...)`. Preserve any other `__*` keys already present.
- [x] 3.2 In `InProcessJobQueueAdapter` (`src/features/background_jobs/adapters/outbound/in_process/adapter.py`), at the handler-invocation site, read `payload.get("__trace", {})`, call `propagator.extract(carrier)`, `token = context.attach(ctx)`, invoke the handler, then `context.detach(token)` in `finally`.
- [x] 3.2a In the arq adapter entrypoint (`src/features/background_jobs/adapters/outbound/arq/adapter.py`) — and any handler-wrapper used in `src/worker.py` — apply the same extract/attach/detach wrapper around the handler call.

## 4. Direct enqueues (non-outbox paths)

- [x] 4.1 Audit `JobQueuePort.enqueue` direct call sites (none expected today after the outbox refactor; verify). For any that remain, inject the carrier inline via the helper from 2.2.

## 5. Tests

- [x] 5.1 Integration: trigger a password-reset → assert the email-send handler's span has the request's `trace_id` (use an in-memory OTel SDK exporter to capture spans).
- [x] 5.2 Unit: in-process queue end-to-end, asserting context propagation across handler boundary.
- [x] 5.3 Unit: payload arriving without `__trace` (legacy row) → handler still runs; no exception; span has a fresh `trace_id`.
- [x] 5.4 Unit: handler that re-enqueues a payload preserves `__trace` verbatim (forward-compat with the reserved-key-preservation contract).

## 6. Docs

- [x] 6.1 Update `docs/outbox.md` to list `__trace` in the reserved-payload-keys table alongside `__outbox_message_id`.
- [x] 6.2 Update `docs/observability.md` with the propagation diagram (request → outbox → relay → handler).

## 7. Wrap-up

- [x] 7.1 `make ci` green.
