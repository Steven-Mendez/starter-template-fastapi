## ADDED Requirements

### Requirement: Outbox carries W3C trace context end-to-end

`outbox_messages` SHALL include a `trace_context: JSONB NOT NULL DEFAULT '{}'::jsonb` column populated at enqueue time via `TraceContextTextMapPropagator().inject(...)`. The relay SHALL forward this carrier to `JobQueuePort.enqueue` under the reserved payload key `__trace`. Job entrypoints (both in-process and arq) SHALL extract the carrier and attach the resulting context before invoking the handler, and detach it in a `finally` block.

#### Scenario: Span hierarchy unified across the queue boundary

- **GIVEN** an in-memory OTel SDK exporter and a request that triggers a password-reset (which enqueues `send_email` via the outbox)
- **WHEN** the relay tick runs and the handler completes
- **THEN** the captured spans include a request-side span, a relay-side span, and a handler-side span
- **AND** all three spans share the same `trace_id`

#### Scenario: Legacy row with empty trace_context still runs

- **GIVEN** an outbox row with `trace_context = '{}'::jsonb` (enqueued before the propagation code shipped)
- **WHEN** the relay dispatches it and the handler runs
- **THEN** the handler completes successfully (no `KeyError`, no propagator error)
- **AND** the handler's span carries a fresh `trace_id` (no parent to attach to)

#### Scenario: Context is detached even when the handler raises

- **GIVEN** a payload carrying a valid `__trace` carrier
- **AND** a handler that raises an exception
- **WHEN** the job entrypoint invokes the handler
- **THEN** the exception propagates to the caller
- **AND** `context.detach(token)` runs in the `finally` block so the active OTel context is restored to what it was before the handler invocation

### Requirement: `__trace` reserved payload key shape

The relay-injected `__trace` payload value SHALL be a JSON object containing a `traceparent` string (W3C format, mandatory when present) and optionally a `tracestate` string. Handlers MUST treat the key as opaque and preserve it when re-enqueuing.

#### Scenario: `__trace` value matches W3C format

- **GIVEN** an active OTel context with a sampled trace
- **WHEN** the relay enqueues a payload
- **THEN** `payload["__trace"]["traceparent"]` matches the W3C regex `^[0-9a-f]{2}-[0-9a-f]{32}-[0-9a-f]{16}-[0-9a-f]{2}$`

#### Scenario: Handler re-enqueue preserves `__trace`

- **GIVEN** a handler that receives a payload with `__trace = {"traceparent": "..."}`
- **WHEN** the handler re-enqueues the payload (manual replay or redrive)
- **THEN** the re-enqueued payload contains the same `__trace` value byte-for-byte
