## MODIFIED Requirements

### Requirement: Outbox row-state machine

Each `outbox_messages` row SHALL move through the state machine `pending → delivered | failed`. `delivered` is the terminal-success state set after `JobQueuePort.enqueue(...)` returns and the row's transaction commits. `failed` is the terminal-dead-letter state set once `attempts ≥ max_attempts`. The timestamp columns `delivered_at` and `failed_at` SHALL be set in the same transaction as the status transition.

#### Scenario: A successful dispatch marks the row delivered

- **GIVEN** a row `r` in `status='pending'`
- **WHEN** the relay claims `r`, enqueues it to the job queue, and commits the transaction
- **THEN** `r.status='delivered'`
- **AND** `r.delivered_at` is set to the commit time
- **AND** `r.failed_at` is `NULL`

#### Scenario: A row that exhausts retries is marked failed

- **GIVEN** a row `r` in `status='pending'` with `attempts = max_attempts - 1`
- **WHEN** the relay attempts to dispatch `r` and `JobQueuePort.enqueue` raises
- **THEN** `r.status='failed'`
- **AND** `r.failed_at` is set
- **AND** `r` is not re-claimed by future ticks

### Requirement: Relay dispatch is at-least-once with per-row commit

The outbox relay SHALL commit each row's `status='delivered'` mark in the same transaction that enqueued the row to the `JobQueuePort`. A crash, network error, or process kill between the enqueue and the commit MUST leave the row in `status='pending'`, eligible for re-claim on the next tick.

The relay MUST inject the row's `OutboxMessage.id` into the enqueued payload under the reserved key `__outbox_message_id`. Outbox-fed job handlers MUST treat this key as a deduplication token: the second invocation with the same value MUST be a no-op returning `Ok(...)`.

#### Scenario: Enqueue failure on one row does not affect siblings

- **GIVEN** three pending outbox rows `r1`, `r2`, `r3`
- **AND** the job queue is configured to raise on `enqueue` for `r2` only
- **WHEN** the relay tick runs
- **THEN** `r1.status='delivered'` and `r3.status='delivered'`
- **AND** `r2.status='pending'` with `r2.attempts=1`
- **AND** the next relay tick after the configured retry delay re-attempts `r2` only

#### Scenario: Crash between enqueue and mark — row re-dispatched once

- **GIVEN** one pending outbox row `r`
- **WHEN** the worker raises after `JobQueuePort.enqueue(...)` returns but before the row's transaction commits
- **AND** the worker restarts and the next relay tick runs
- **THEN** `r.status='delivered'` after the second tick
- **AND** the handler observed exactly one effective side effect (the second handler invocation was a no-op thanks to `__outbox_message_id` dedup)

#### Scenario: Handler dedups by `__outbox_message_id`

- **GIVEN** a handler `send_email` that wraps its side effect in an insert into `processed_outbox_messages`
- **WHEN** the handler is invoked twice with the same `__outbox_message_id` payload
- **THEN** exactly one email is sent
- **AND** both invocations return `Ok(...)`

### Requirement: Reserved payload key namespace

The relay SHALL own the `__*` prefix inside the job payload. Non-reserved keys are the original handler payload and MUST NOT be modified by the relay. Handlers re-enqueuing a payload (manual replay, redrive tooling) MUST preserve every `__*` key they received unchanged. This change introduces `__outbox_message_id`; sibling changes layer additional reserved keys (e.g. `__trace` from `propagate-trace-context-through-jobs`).

#### Scenario: Relay does not mutate non-reserved payload keys

- **GIVEN** a row enqueued with payload `{"to": "user@example.com", "template": "verify"}`
- **WHEN** the relay dispatches it
- **THEN** the handler observes a payload whose non-`__*` keys are exactly `{"to": "user@example.com", "template": "verify"}`
- **AND** the payload also contains `__outbox_message_id` equal to the row's id

#### Scenario: Re-enqueue preserves unknown reserved keys

- **GIVEN** a handler receives a payload containing a reserved key the handler does not understand (e.g. `__trace`)
- **WHEN** the handler re-enqueues the payload (replay or redrive)
- **THEN** the re-enqueued payload still contains that reserved key with its original value

### Requirement: Retry backoff is exponential and capped

When the relay marks a row for retry (handler-side dispatch failure or relay-side enqueue failure), it SHALL compute the next `available_at` as `now() + min(retry_base * 2^(next_attempts - 1), retry_max)`. `retry_base` and `retry_max` are configurable via `APP_OUTBOX_RETRY_BASE_SECONDS` (default 30s) and `APP_OUTBOX_RETRY_MAX_SECONDS` (default 900s).

#### Scenario: Retry delays grow exponentially up to the cap

- **GIVEN** `retry_base=30`, `retry_max=900`, a row that fails on every attempt
- **WHEN** the relay processes the row across attempts 1 through 8
- **THEN** the deltas between successive `available_at` values are approximately `30, 60, 120, 240, 480, 900, 900` (capped at `retry_max` from attempt 6 onward)

#### Scenario: A successful retry stops the backoff progression

- **GIVEN** `retry_base=30`, a row that fails on attempt 1 and succeeds on attempt 2
- **WHEN** the relay processes both attempts
- **THEN** after attempt 1 `available_at` is advanced by ~30s and `attempts=1`
- **AND** after attempt 2 the row is `delivered` and `available_at` is not advanced further

### Requirement: Pending-row index has a tiebreaker

The partial index supporting the relay claim query SHALL be on `(available_at, id) WHERE status='pending'`. The claim query MUST `ORDER BY available_at, id` to match the index.

#### Scenario: Index definition is correct in the deployed schema

- **GIVEN** an alembic-migrated database
- **WHEN** the test queries `pg_indexes` for the table `outbox_messages`
- **THEN** an index named `ix_outbox_pending` exists with a definition matching `(available_at, id) WHERE status='pending'`

#### Scenario: Two pending rows with the same `available_at` claim in a stable order

- **GIVEN** two pending rows `r_a` and `r_b` with identical `available_at` and `r_a.id < r_b.id`
- **WHEN** the relay issues its claim query with `LIMIT 1`
- **THEN** `r_a` is claimed before `r_b`
- **AND** the SKIP LOCKED scan order is deterministic across repeated executions
