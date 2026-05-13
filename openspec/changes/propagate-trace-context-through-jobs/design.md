## Context

OTel context propagation across async boundaries (queues, jobs, RPCs) is documented in the spec — we just haven't applied it. Two carriers exist: the outbox row (durable) and the job payload (transient). We use both: the row for "this is the request that produced this side effect" forever; the payload to carry it to the handler.

## Depends on

- **fix-outbox-dispatch-idempotency** — must land first. It defines the per-row dispatch transaction, the reserved-payload-key namespace (`__*`), and the `delivered`/`failed` state machine this change builds on.
- **improve-otel-instrumentation** (soft) — provides `@traced` decorator and the configured sampler ratio. Without it the handler still attaches context correctly; the spans just may not get sampled coherently with the request side.

## Conflicts with

- **fix-outbox-dispatch-idempotency** — same `dispatch_pending.py` + `outbox/models.py`. Sequenced after.
- **add-outbox-retention-prune** — same `src/worker.py` cron-registration surface; both must respect the reserved-payload-key contract (prune is opaque to `__trace`, just deletes rows by retention age).
- **schedule-token-cleanup** — also registers an arq cron on `src/worker.py`. Distinct cron — merge-friction only.

## Reserved payload keys (cluster-wide contract)

Sibling contract documented identically in every outbox-cluster change. The relay owns the `__*` prefix; everything else is the handler's original payload. Handlers MUST round-trip unknown reserved keys when re-enqueuing.

| Key | Introduced by | Type / shape |
|---|---|---|
| `__outbox_message_id` | `fix-outbox-dispatch-idempotency` | str — `OutboxMessage.id` (UUID) |
| `__trace` | this change | `{"traceparent": str, "tracestate": str?}` (W3C) |

## Non-goals

- Baggage propagation across the queue boundary. Only the W3C `traceparent`/`tracestate` pair is carried; baggage is a follow-up.
- Log correlation (injecting `trace_id`/`span_id` into log records). Handled separately by the observability instrumentation work.
- Cross-trace linking on retries. A re-enqueued payload simply replays the original carrier; we do not add `links` to the new span.
- Propagation across non-`JobQueuePort` async boundaries (HTTP egress, SMTP). Those use their own instrumentation.
- Sampling decisions. The propagator faithfully carries the upstream `traceparent` flags; the sampler itself is configured elsewhere.

## Decisions

- **Two storage locations**: `outbox_messages.trace_context` column (durable, queryable from operator tools) + `payload.__trace` (transient, what the handler actually reads). Belt-and-suspenders, no duplication of effort since the relay copies the column into the payload key at dispatch time.
- **Reserved key `__trace`**: matches the existing `__outbox_message_id` reserved-key convention. Single short key keeps payload overhead low; the value is the W3C carrier dict the propagator emits.
- **W3C propagator format**: `traceparent` (mandatory) + optional `tracestate`. Cross-vendor compatible. We do not store baggage in this change; baggage propagation is a follow-up.
- **Column default `'{}'::jsonb NOT NULL`**: legacy rows enqueued before the migration land have an empty carrier; the relay tolerates empty maps (extract returns the current context, which produces a fresh trace — same behavior as today).

## Risks / Trade-offs

- **Risk**: an upgrade lands the code-side change without the migration; legacy rows have no `trace_context`. Mitigation: column default is `'{}'::jsonb NOT NULL`; relay tolerates empty maps (just doesn't propagate).
- **Risk**: a handler that doesn't know about `__trace` strips it on re-enqueue. Mitigation: the reserved-key-preservation requirement is codified in the idempotency change's spec; this change's tests assert it for `__trace`.
- **Trade-off**: tiny payload overhead per job (~150 bytes). Acceptable.

## Migration Plan

Single PR, sequenced after `fix-outbox-dispatch-idempotency` lands. Order inside this PR:

1. Schema migration (`trace_context JSONB NOT NULL DEFAULT '{}'`).
2. `SessionSQLModelOutboxAdapter.enqueue` injects the carrier into the column.
3. `DispatchPending` copies the column into `payload.__trace` before calling `JobQueuePort.enqueue`.
4. In-process + arq adapters extract `__trace` and attach context around the handler.
5. Tests.

Rollback: drop the column, revert the code. `__trace` is additive; older handlers ignore it.
