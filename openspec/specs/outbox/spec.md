# outbox Specification

## Purpose
TBD - created by archiving change add-outbox-pattern. Update Purpose after archive.
## Requirements
### Requirement: Atomic enqueue with business state

The system SHALL expose an `OutboxPort.enqueue(job_name, payload, *, available_at=None)` method that records a pending side effect in the same SQL transaction as the caller's business writes. The recorded row SHALL become visible to the relay only if and only if the caller's transaction commits; a rollback SHALL leave no trace of the enqueue.

#### Scenario: Enqueue and commit deliver exactly one row

- **WHEN** a use case opens a unit-of-work, writes a domain row, calls `OutboxPort.enqueue(job_name="send_email", payload={"to": "...", ...})`, and commits the unit-of-work
- **THEN** exactly one row appears in `outbox_messages` with `status='pending'`, `job_name='send_email'`, and the supplied payload, and the domain row is also visible

#### Scenario: Enqueue and rollback deliver nothing

- **WHEN** a use case opens a unit-of-work, calls `OutboxPort.enqueue(...)`, and rolls the unit-of-work back
- **THEN** no row appears in `outbox_messages` and the side effect is not dispatched

#### Scenario: Future `available_at` schedules the row

- **WHEN** a use case calls `OutboxPort.enqueue(..., available_at=<future timestamp>)` and commits
- **THEN** the row is written with the supplied `available_at` and the relay SHALL NOT claim it until `now() >= available_at`

### Requirement: At-least-once delivery via the relay

The system SHALL provide an `OutboxRelay` that, running inside the background worker process, periodically claims `pending` rows whose `available_at` has passed and dispatches each via `JobQueuePort.enqueue(job_name, payload)`. Delivery SHALL be at-least-once: a row MAY be dispatched more than once across worker restarts or failures, but a `pending` row whose `available_at` has passed SHALL eventually be dispatched while at least one worker is running.

#### Scenario: A pending row is dispatched and marked dispatched

- **WHEN** an `outbox_messages` row exists with `status='pending'` and `available_at <= now()` and a worker runs a relay tick
- **THEN** the relay calls `JobQueuePort.enqueue(job_name, payload)` exactly once for that row in the success path, and on success updates the row to `status='dispatched'` with `dispatched_at = now()`

#### Scenario: Multiple workers do not double-claim a row

- **WHEN** two worker replicas execute the relay claim concurrently against the same database
- **THEN** each `pending` row is observed by at most one relay tick per cycle, because the claim query uses `FOR UPDATE SKIP LOCKED`

#### Scenario: Worker crash between dispatch and mark

- **WHEN** a worker claims a row, calls `JobQueuePort.enqueue` successfully, and crashes before marking the row `dispatched`
- **THEN** on recovery the row is still `status='pending'` and is dispatched again — i.e. the contract is at-least-once, not exactly-once, and consumer handlers MUST be idempotent

### Requirement: Retry and permanent failure

The system SHALL retry a row whose dispatch raises an exception by incrementing `attempts`, recording `last_error`, and setting `available_at = now() + <retry_delay>`. Once `attempts >= APP_OUTBOX_MAX_ATTEMPTS` the row SHALL be flipped to `status='failed'` and SHALL NOT be claimed by subsequent relay ticks.

#### Scenario: Transient dispatch failure schedules a retry

- **WHEN** the relay claims a row and `JobQueuePort.enqueue` raises an exception
- **THEN** the row's `attempts` is incremented, `last_error` is set to the exception representation, `available_at` is advanced by the configured retry delay, and `status` remains `pending`

#### Scenario: Exceeded max attempts becomes failed

- **WHEN** a row's `attempts` is one below `APP_OUTBOX_MAX_ATTEMPTS` and dispatch fails again
- **THEN** the row is updated to `status='failed'` with `last_error` populated, and the relay SHALL NOT include the row in subsequent claim queries

### Requirement: SQLModel adapter session scoping

The SQLModel implementation of `OutboxPort` SHALL operate against the SQLModel `Session` already in use by the calling unit-of-work, not against an independently opened session or engine. The adapter SHALL NOT call `session.commit()` or `session.rollback()` on its own — those remain the responsibility of the unit-of-work.

#### Scenario: Adapter writes on the caller's session

- **WHEN** a unit-of-work passes its `Session` into the session-scoped outbox adapter and the caller invokes `OutboxPort.enqueue(...)`
- **THEN** the resulting `INSERT` is staged on that `Session` and becomes visible only after the unit-of-work commits

#### Scenario: Adapter does not commit on its own

- **WHEN** the unit-of-work has not yet committed and `OutboxPort.enqueue` returns
- **THEN** the `outbox_messages` row is not visible to a separate transaction

### Requirement: In-memory fake for unit and e2e tests

The system SHALL provide an in-memory `OutboxPort` fake suitable for unit and e2e tests. The fake SHALL dispatch each enqueued payload to a registered handler dispatcher exactly once **after** the test's explicit commit hook fires, mirroring the in-process job-queue ergonomics but preserving the transactional contract (no dispatch on rollback).

#### Scenario: Fake outbox dispatches on commit

- **WHEN** a test enqueues a payload through the fake `OutboxPort` and then calls the unit-of-work's commit hook
- **THEN** the fake dispatches the payload by invoking the registered handler dispatcher exactly once

#### Scenario: Fake outbox suppresses dispatch on rollback

- **WHEN** a test enqueues a payload through the fake `OutboxPort` and then calls the unit-of-work's rollback hook (or never commits)
- **THEN** the fake does not invoke any handler dispatcher

### Requirement: Per-feature settings projection and production validator

The system SHALL ship an `OutboxSettings` projection with fields `enabled` (bool), `relay_interval_seconds` (float), `claim_batch_size` (int), `max_attempts` (int), and `worker_id` (string). `OutboxSettings.validate_production` SHALL append an error when `enabled` is `false`, refusing startup with `APP_ENVIRONMENT=production` and `APP_OUTBOX_ENABLED=false`.

#### Scenario: Production startup refuses the disabled outbox

- **WHEN** the application boots with `APP_ENVIRONMENT=production` and `APP_OUTBOX_ENABLED=false`
- **THEN** `AppSettings._validate_production_settings` SHALL include "APP_OUTBOX_ENABLED must be true in production" (or equivalent) and raise `ValueError` before any feature container is built

#### Scenario: Non-production startup tolerates the disabled outbox

- **WHEN** the application boots with `APP_ENVIRONMENT=development` and `APP_OUTBOX_ENABLED=false`
- **THEN** the application boots normally, the relay does not register itself with the worker, and the in-memory fake (in tests) or a no-op SQLModel adapter handles `OutboxPort.enqueue` calls without raising

### Requirement: Worker integration

The worker entrypoint (`src/worker.py`) SHALL register the relay as a recurring task on the shared `arq` worker when `APP_OUTBOX_ENABLED=true`. The web process (`src/main.py`) SHALL NOT register or run the relay loop.

#### Scenario: Worker boots the relay loop when enabled

- **WHEN** `src/worker.py` starts with `APP_OUTBOX_ENABLED=true`
- **THEN** the relay is scheduled to run every `APP_OUTBOX_RELAY_INTERVAL_SECONDS` seconds, claims up to `APP_OUTBOX_CLAIM_BATCH_SIZE` rows per tick, and dispatches them through `JobQueuePort`

#### Scenario: Web process never runs the relay

- **WHEN** `src/main.py` boots regardless of `APP_OUTBOX_ENABLED`
- **THEN** the FastAPI process SHALL NOT start the relay loop or claim outbox rows

### Requirement: Cross-feature isolation

The outbox feature SHALL NOT import any other feature's modules. Other features SHALL interact with it only through `OutboxPort`. The authentication feature SHALL be forbidden from importing `src.features.background_jobs.adapters` directly so its request-path enqueues are forced through the outbox.

#### Scenario: Import Linter rejects outbox → feature imports

- **WHEN** any module under `src.features.outbox.*` imports from `src.features.<other_feature>`
- **THEN** `make lint-arch` SHALL fail with the corresponding contract violation

#### Scenario: Import Linter rejects auth use cases that bypass the outbox

- **WHEN** any module under `src.features.authentication.application` or `src.features.authentication.adapters.inbound` imports from `src.features.background_jobs.adapters`
- **THEN** `make lint-arch` SHALL fail with the corresponding contract violation

### Requirement: Authentication request-path consumers go through the outbox

The use cases `RequestPasswordReset` and `RequestEmailVerification` SHALL enqueue the `send_email` job through `OutboxPort.enqueue`, not through `JobQueuePort.enqueue`, so that the verification/reset token row and the email-send intent commit atomically.

#### Scenario: Password-reset row and email-send intent commit together

- **WHEN** `RequestPasswordReset` writes a password-reset token row and enqueues the `send_email` job
- **THEN** both writes go through the same unit-of-work and a single commit makes both visible

#### Scenario: Failed password-reset transaction does not enqueue an email

- **WHEN** `RequestPasswordReset` raises an exception after enqueueing the email but before the unit-of-work commits
- **THEN** no `outbox_messages` row is committed and no email is dispatched

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

### Requirement: Outbox and dedup tables have a retention policy

A `PruneOutbox` use case SHALL delete:
- `outbox_messages` rows where `status='delivered' AND delivered_at < now() - APP_OUTBOX_RETENTION_DELIVERED_DAYS`.
- `outbox_messages` rows where `status='failed' AND failed_at < now() - APP_OUTBOX_RETENTION_FAILED_DAYS`.
- `processed_outbox_messages` rows where `processed_at < now() - 2 × APP_OUTBOX_RETRY_MAX_SECONDS`.

Deletions SHALL be batched in groups of at most `APP_OUTBOX_PRUNE_BATCH_SIZE` rows (default 1000) per transaction; the use case SHALL loop internally until the matching set is empty. The worker SHALL schedule `PruneOutbox.execute(...)` every 1 hour while `APP_OUTBOX_ENABLED=true`.

#### Scenario: Old delivered rows are removed; recent ones survive

- **GIVEN** 500 rows with `status='delivered'` and `delivered_at = now() - 30 days`
- **AND** 50 rows with `status='delivered'` and `delivered_at = now() - 1 day`
- **WHEN** the prune runs with `retention_delivered_days=7`
- **THEN** all 500 old rows are deleted
- **AND** all 50 recent rows remain

#### Scenario: Old failed rows obey their separate retention

- **GIVEN** 100 rows with `status='failed'` and `failed_at = now() - 40 days`
- **AND** 20 rows with `status='failed'` and `failed_at = now() - 25 days`
- **WHEN** the prune runs with `retention_failed_days=30`
- **THEN** the 100 rows older than 30 days are deleted
- **AND** the 20 rows newer than 30 days remain

#### Scenario: Dedup table is pruned at 2× retry window

- **GIVEN** `APP_OUTBOX_RETRY_MAX_SECONDS=900` (15 minutes)
- **AND** 200 `processed_outbox_messages` rows with `processed_at = now() - 1 hour`
- **AND** 50 `processed_outbox_messages` rows with `processed_at = now() - 5 minutes`
- **WHEN** the prune runs
- **THEN** the 200 rows older than 30 minutes are deleted
- **AND** the 50 recent rows remain

#### Scenario: Batch size bounds each transaction

- **GIVEN** `APP_OUTBOX_PRUNE_BATCH_SIZE=1000`
- **AND** 2500 `delivered` rows are eligible for deletion
- **WHEN** the prune runs
- **THEN** all 2500 rows are deleted across at least 3 internal transactions
- **AND** no single `DELETE` statement removes more than 1000 rows

#### Scenario: Mid-batch failure leaves remaining rows eligible for the next tick

- **GIVEN** 2500 `delivered` rows eligible for deletion and `prune_batch_size=1000`
- **AND** the second batch's transaction fails with a transient database error
- **WHEN** the prune runs
- **THEN** the first batch's 1000 rows have been deleted
- **AND** the remaining ~1500 rows still satisfy the eligibility predicate
- **AND** the next prune tick deletes them
- **AND** the relay's claim query for `pending` rows is unaffected (disjoint row set)

#### Scenario: Prune is opaque to non-pending rows' payloads

- **GIVEN** a `delivered` row whose `payload` contains arbitrary reserved keys (e.g. `__outbox_message_id`, `__trace`)
- **WHEN** the prune evaluates the row for deletion
- **THEN** the decision is based solely on `status` and `delivered_at`
- **AND** the payload is not read or modified

### Requirement: PruneOutbox is invocable as a one-shot CLI

`src/cli/outbox_prune.py` SHALL invoke the same `PruneOutbox` use case as the worker cron, using the same settings projection, and print a summary of rows deleted per table.

#### Scenario: Operator runs `make outbox-prune`

- **GIVEN** a configured environment with eligible rows in the database
- **WHEN** the operator runs `make outbox-prune`
- **THEN** the process exits with code 0
- **AND** stdout reports the number of rows deleted from each of `outbox_messages` (delivered), `outbox_messages` (failed), and `processed_outbox_messages`
