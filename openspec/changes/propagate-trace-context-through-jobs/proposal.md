## Why

`grep -rn 'TraceContextTextMapPropagator|carrier|inject|traceparent'` returns nothing. `OutboxPort.enqueue` accepts only `payload: dict`; the arq adapter passes the payload verbatim. The originating request's `traceparent` is never injected, so every job span starts a brand-new trace, breaking the **request → outbox → relay → handler → email** causal chain. Operators investigating a slow password-reset flow cannot follow it across the queue boundary.

## What Changes

- Add a `trace_context: JSONB` column on `outbox_messages` (populated via `TraceContextTextMapPropagator.inject(carrier={})` at `enqueue` time).
- In the relay, before invoking `JobQueuePort.enqueue`, embed the carrier into the payload under the reserved key `__trace` (alongside `__outbox_message_id` introduced by `fix-outbox-dispatch-idempotency`).
- In the arq job entrypoint (and the in-process adapter), `propagator.extract(carrier=payload.get("__trace", {}))` and `attach()` it before calling the handler, so the handler's spans are children of the originating request's trace.
- Same pattern for any direct `JobQueuePort.enqueue` call site that bypasses the outbox.

## Depends on

- **fix-outbox-dispatch-idempotency** — must land first. This change extends the reserved-payload-key contract (`__*` namespace) defined there, and the relay-side injection point lives inside the per-row dispatch transaction it restructures.
- **improve-otel-instrumentation** (soft) — provides the sampler/`@traced` infrastructure consumed by the handler-side extract.

## Conflicts with

- **fix-outbox-dispatch-idempotency** — co-edits `src/features/outbox/application/use_cases/dispatch_pending.py` and `src/features/outbox/adapters/outbound/sqlmodel/models.py`. Sequenced after that change.
- **add-outbox-retention-prune** — co-edits `src/worker.py` (cron registration). Both must be aware of the reserved-payload-key contract; prune treats `__trace` as opaque.

## Reserved payload keys (shared contract across the outbox cluster)

The relay reserves the `__*` namespace inside the job payload. Non-reserved keys are the original handler payload, untouched. Handlers MUST preserve unknown reserved keys when re-enqueuing on retry.

| Key | Introduced by | Type / shape |
|---|---|---|
| `__outbox_message_id` | `fix-outbox-dispatch-idempotency` | str — `OutboxMessage.id` (UUID); handlers dedup on it |
| `__trace` | this change | `{"traceparent": str, "tracestate": str?}` (W3C) |

**Capabilities — Modified**: `outbox` (extends the reserved-payload-key contract; adds a `trace_context` column).

## Impact

- **Migrations**: one Alembic revision under `alembic/versions/` adding `outbox_messages.trace_context JSONB NOT NULL DEFAULT '{}'::jsonb`.
- **Code**: `src/features/outbox/adapters/outbound/sqlmodel/models.py`, `src/features/outbox/adapters/outbound/sqlmodel/repository.py` (`SessionSQLModelOutboxAdapter.enqueue`), `src/features/outbox/application/use_cases/dispatch_pending.py`, `src/features/background_jobs/adapters/outbound/in_process/adapter.py`, `src/features/background_jobs/adapters/outbound/arq/adapter.py`, `src/worker.py` (entry-point context attach/detach), `src/app_platform/observability/tracing.py` (propagator helper).
- **Docs**: `docs/outbox.md`, `docs/observability.md`.
- **Tests**: end-to-end assertion that a request-initiated trace spans request → relay → handler with the same `trace_id`.
