## MODIFIED Requirements

### Requirement: Worker integration

The worker composition-root scaffold (`src/worker.py`) SHALL collect the relay cron descriptor (and the `outbox-prune` descriptor) when `APP_OUTBOX_ENABLED=true`, declaring the schedule once for a future job runtime to bind. The web process (`src/main.py`) SHALL NOT register or run the relay loop. `src/worker.py` SHALL NOT import `arq`. The `APP_OUTBOX_ENABLED=true` production refusal is unchanged: request-path consumers write to the outbox unconditionally, so production with deferred work is intentionally not bootable until the production job runtime (AWS SQS + a Lambda worker) is added at a later roadmap step — the `outbox_messages` table and its request-path writers are unchanged; only the runtime that drains it is removed.

#### Scenario: Worker scaffold collects the relay descriptor when enabled

- **WHEN** `src/worker.py` builds the scaffold with `APP_OUTBOX_ENABLED=true`
- **THEN** an `outbox-relay` cron descriptor is collected with the configured `APP_OUTBOX_RELAY_INTERVAL_SECONDS` (snapped to a divisor of 60) and an `outbox-prune` descriptor is collected for the hourly trim
- **AND** the descriptors are runtime-agnostic (no `arq` `CronJob`) so a future scheduler can bind them
- **AND** no relay tick runs (no job runtime is wired until a later roadmap step)

#### Scenario: Relay descriptor absent when the outbox is disabled

- **WHEN** the scaffold is built with `APP_OUTBOX_ENABLED=false`
- **THEN** no relay or prune cron descriptor is collected (the builder returns an empty sequence)

#### Scenario: Web process never runs the relay

- **WHEN** `src/main.py` boots regardless of `APP_OUTBOX_ENABLED`
- **THEN** the FastAPI process SHALL NOT start the relay loop or claim outbox rows

### Requirement: Outbox carries W3C trace context end-to-end

`outbox_messages` SHALL include a `trace_context: JSONB NOT NULL DEFAULT '{}'::jsonb` column populated at enqueue time via `TraceContextTextMapPropagator().inject(...)`. The relay SHALL forward this carrier to `JobQueuePort.enqueue` under the reserved payload key `__trace`. The in-process job entrypoint SHALL extract the carrier and attach the resulting context before invoking the handler, and detach it in a `finally` block.

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
- **WHEN** the in-process job entrypoint invokes the handler
- **THEN** the exception propagates to the caller
- **AND** `context.detach(token)` runs in the `finally` block so the active OTel context is restored to what it was before the handler invocation
