# background-jobs Specification

## Purpose
TBD - created by archiving change starter-template-foundation. Update Purpose after archive.
## Requirements
### Requirement: Background-jobs is a self-contained feature slice

The system SHALL host background-job concerns in a dedicated feature slice at `src/features/background_jobs/`. The slice SHALL contain the `JobQueuePort` inbound port, the `in_process` adapter (synchronous; for dev/test), the `arq` adapter (Redis-backed; for production), the worker entrypoint, and the registry through which features contribute their job handlers.

#### Scenario: Background-jobs owns its port and adapters

- **WHEN** the codebase is loaded
- **THEN** `src/features/background_jobs/application/ports/job_queue_port.py` defines `JobQueuePort` as a Protocol with `enqueue(job_name, payload)` and `enqueue_at(job_name, payload, run_at)`
- **AND** `src/features/background_jobs/adapters/outbound/in_process/` and `src/features/background_jobs/adapters/outbound/arq/` each contain an adapter that implements `JobQueuePort`

#### Scenario: Background-jobs does not import from other features

- **WHEN** the codebase is loaded
- **THEN** no module under `src/features/background_jobs/` imports from any other `src/features/<name>/` directory

### Requirement: Adapter selection by configuration with production guard

The system SHALL select the queue adapter at startup from `APP_JOBS_BACKEND`, which accepts `in_process` or `arq`. When `arq` is selected, `APP_JOBS_REDIS_URL` SHALL be required. Production validation SHALL refuse `in_process` when `APP_ENVIRONMENT=production`.

#### Scenario: In-process adapter runs jobs synchronously

- **GIVEN** `APP_JOBS_BACKEND=in_process`
- **WHEN** `JobQueuePort.enqueue("send_email", {...})` is called
- **THEN** the registered handler for `send_email` is invoked inline before `enqueue` returns
- **AND** any handler exception propagates to the caller

#### Scenario: Production refuses the in-process adapter

- **GIVEN** `APP_JOBS_BACKEND=in_process` and `APP_ENVIRONMENT=production`
- **WHEN** the application starts
- **THEN** startup fails with a settings validation error naming `APP_JOBS_BACKEND`

#### Scenario: arq adapter requires Redis URL

- **GIVEN** `APP_JOBS_BACKEND=arq` and `APP_JOBS_REDIS_URL` is unset
- **WHEN** the application starts
- **THEN** startup fails with a settings validation error naming `APP_JOBS_REDIS_URL`

### Requirement: Features register their job handlers at composition time

Each feature that owns a background job SHALL register its handler with a `JobHandlerRegistry` at composition. The registry SHALL be sealed before the worker (or the web app, when running `in_process`) starts processing. The queue SHALL refuse to enqueue a job whose name is not registered.

#### Scenario: Email feature registers SendEmailJob

- **WHEN** `build_email_container(...)` returns
- **THEN** the job handler registry contains an entry for `send_email`
- **AND** the entry resolves to a callable that consumes the payload and calls the configured `EmailPort` adapter

#### Scenario: Enqueueing an unregistered job fails

- **WHEN** `JobQueuePort.enqueue("not-a-real-job", {})` is called
- **THEN** the call raises `UnknownJobError`
- **AND** the queue state is unchanged

### Requirement: A worker entrypoint is available

The repository SHALL provide a `make worker` target that starts an `arq` worker bound to the same `APP_JOBS_REDIS_URL` the web app uses. The worker SHALL load the same composition root (same job handler registry) so handlers registered by features are available without duplication.

#### Scenario: make worker starts arq with the registered handlers

- **GIVEN** `APP_JOBS_BACKEND=arq` and `APP_JOBS_REDIS_URL` set to a reachable Redis
- **WHEN** `make worker` runs
- **THEN** the process binds to the configured Redis queue
- **AND** the worker logs the names of every registered job handler at startup

#### Scenario: A SendEmailJob enqueued by the web app is processed by the worker

- **GIVEN** a running worker
- **WHEN** the web app enqueues `send_email` with a valid payload
- **THEN** the worker invokes the registered handler within one polling cycle
- **AND** the rendered email is sent via the configured `EmailPort` adapter
