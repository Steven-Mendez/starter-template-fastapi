## ADDED Requirements

### Requirement: arq worker has bounded result retention with per-handler override

`WorkerSettings` SHALL set `max_jobs` and `job_timeout` from configured values (defaults: 16 and 600 seconds). Each handler's `keep_result` SHALL default to `keep_result_seconds_default` (300) and SHALL be overridable per-handler via an explicit `keep_result_seconds` argument at registration time. The platform default SHALL be configurable via `APP_JOBS_KEEP_RESULT_SECONDS_DEFAULT`. `docs/background-jobs.md` SHALL document the recommended Redis eviction policy (`maxmemory-policy allkeys-lru`).

#### Scenario: Handler without override picks the platform default

- **GIVEN** a handler registered with `JobHandlerRegistry.register("send_email", handler)` (no `keep_result_seconds` argument)
- **WHEN** the worker boots
- **THEN** the arq `Function` for `send_email` has `keep_result == 300`

#### Scenario: Handler with explicit override picks the override value

- **GIVEN** a handler registered with `JobHandlerRegistry.register("billing_charge", handler, keep_result_seconds=86400)`
- **WHEN** the worker boots
- **THEN** the arq `Function` for `billing_charge` has `keep_result == 86400`

#### Scenario: Settings override the platform default

- **GIVEN** `APP_JOBS_KEEP_RESULT_SECONDS_DEFAULT=600`
- **WHEN** the worker boots
- **THEN** every handler without an explicit override has `Function.keep_result == 600`

#### Scenario: max_jobs and job_timeout flow into WorkerSettings

- **GIVEN** `APP_JOBS_MAX_JOBS=32` and `APP_JOBS_JOB_TIMEOUT_SECONDS=900`
- **WHEN** the worker boots
- **THEN** `WorkerSettings.max_jobs == 32` and `WorkerSettings.job_timeout == 900`

#### Scenario: Handler exceeding job_timeout is cancelled

- **GIVEN** a handler registered with the default `job_timeout_seconds=600`
- **WHEN** an enqueued invocation runs for more than 600 seconds
- **THEN** arq cancels the task and records a failure
- **AND** the worker process remains available to pick up the next job (not pinned by the hung handler)
