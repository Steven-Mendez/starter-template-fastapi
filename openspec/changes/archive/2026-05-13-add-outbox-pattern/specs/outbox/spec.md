## ADDED Requirements

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
