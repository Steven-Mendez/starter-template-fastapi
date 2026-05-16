## MODIFIED Requirements

### Requirement: Background-jobs is a self-contained feature slice

The system SHALL host background-job concerns in a dedicated feature slice at `src/features/background_jobs/`. The slice SHALL contain the `JobQueuePort` inbound port, the `in_process` adapter (synchronous; for dev/test, and the only shipped adapter), a runtime-agnostic worker composition-root scaffold, and the registry through which features contribute their job handlers and recurring cron descriptors. There SHALL be no `arq` adapter and no `arq` import anywhere in the codebase: the `arq` backend and its worker runtime are removed (ROADMAP ETAPA I step 5). The production job runtime (AWS SQS + a Lambda worker) is added at a later roadmap step.

#### Scenario: Background-jobs owns its port and the in-process adapter

- **WHEN** the codebase is loaded
- **THEN** `src/features/background_jobs/application/ports/job_queue_port.py` defines `JobQueuePort` as a Protocol with `enqueue(job_name, payload)` and `enqueue_at(job_name, payload, run_at)`
- **AND** `src/features/background_jobs/adapters/outbound/in_process/` contains an adapter that implements `JobQueuePort`
- **AND** `src/features/background_jobs/adapters/outbound/arq/` does not exist

#### Scenario: No arq import remains

- **WHEN** the codebase, `pyproject.toml` dependency declarations, and `.env.example` are loaded
- **THEN** no module under `src/` imports `arq` (no `from arq ...`, no `import arq`)
- **AND** no `[project.optional-dependencies]` extra and no `dev` dependency-group entry declares `arq`

#### Scenario: Background-jobs does not import from other features

- **WHEN** the codebase is loaded
- **THEN** no module under `src/features/background_jobs/` imports from any other `src/features/<name>/` directory

### Requirement: Adapter selection by configuration with production guard

The system SHALL select the queue adapter at startup from `APP_JOBS_BACKEND`, which accepts only `in_process`. Production validation SHALL refuse `in_process` when `APP_ENVIRONMENT=production`, and no job backend SHALL be accepted in production: there is no production job runtime until the AWS SQS adapter and the Lambda worker are added at a later roadmap step. The production refusal message SHALL NOT name `arq` or `APP_JOBS_REDIS_URL`.

#### Scenario: In-process adapter runs jobs synchronously

- **GIVEN** `APP_JOBS_BACKEND=in_process`
- **WHEN** `JobQueuePort.enqueue("send_email", {...})` is called
- **THEN** the registered handler for `send_email` is invoked inline before `enqueue` returns
- **AND** any handler exception propagates to the caller

#### Scenario: Production refuses the in-process adapter without an accept-path

- **GIVEN** `APP_JOBS_BACKEND=in_process` (the only accepted value) and `APP_ENVIRONMENT=production`
- **WHEN** the application starts
- **THEN** startup fails with a settings validation error naming `APP_JOBS_BACKEND`
- **AND** the error message does NOT instruct the operator to configure `arq` or set `APP_JOBS_REDIS_URL`
- **AND** no job backend is accepted in production

### Requirement: Features register their job handlers at composition time

Each feature that owns a background job SHALL register its handler with a `JobHandlerRegistry` at composition. The registry SHALL be sealed before job processing begins (by the web app when running `in_process`, and by the future job runtime). The queue SHALL refuse to enqueue a job whose name is not registered.

#### Scenario: Email feature registers SendEmailJob

- **WHEN** `build_email_container(...)` returns
- **THEN** the job handler registry contains an entry for `send_email`
- **AND** the entry resolves to a callable that consumes the payload and calls the configured `EmailPort` adapter

#### Scenario: Enqueueing an unregistered job fails

- **WHEN** `JobQueuePort.enqueue("not-a-real-job", {})` is called
- **THEN** the call raises `UnknownJobError`
- **AND** the queue state is unchanged

### Requirement: A worker entrypoint is available

The repository SHALL provide a `make worker` target and a `src/worker.py` module that load the same composition root the web app uses (same `JobHandlerRegistry`, same handlers, same outbox-relay and auth-maintenance cron descriptors), so handlers and schedules are declared once and shared. `src/worker.py` SHALL NOT import `arq`, construct an `arq` `WorkerSettings`, or call `arq.run_worker`. Until the production job runtime (AWS SQS + a Lambda worker, a later roadmap step) is wired, `make worker` SHALL build the scaffold (so composition errors still surface loudly), log the registered handlers and collected cron descriptors, and exit with a non-zero status and a clear message stating that no job runtime is wired yet.

#### Scenario: make worker builds the scaffold and exits honestly

- **GIVEN** a clean checkout with `APP_JOBS_BACKEND=in_process`
- **WHEN** `make worker` runs
- **THEN** the process builds the shared composition root and logs the names of every registered job handler and cron descriptor
- **AND** it exits with a non-zero status and a message stating no job runtime is wired (the AWS SQS + Lambda worker arrives at a later roadmap step)
- **AND** the process never imports `arq` and never binds a Redis queue

#### Scenario: The shared composition root is preserved for the future runtime

- **WHEN** `src/worker.py` is loaded
- **THEN** it builds the same email/jobs/outbox/users containers as today, registers `send_email`, `delete_user_assets`, and `erase_user` with their outbox-backed dedupe, seals the registry, and collects the relay + auth-purge cron descriptors
- **AND** the engine-dispose / Redis-close / tracing-flush drain helpers remain callable so a future runtime can re-bind them
