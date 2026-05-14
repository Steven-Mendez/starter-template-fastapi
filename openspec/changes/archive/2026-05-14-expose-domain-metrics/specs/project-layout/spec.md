## ADDED Requirements

### Requirement: Metrics use OpenTelemetry meters via a central factory

The application SHALL emit metrics through OpenTelemetry meters obtained from `app_platform.observability.metrics.get_app_meter(feature)`. Features MUST NOT call `opentelemetry.metrics.get_meter` directly, and the project MUST NOT introduce new uses of `prometheus_client`. `/metrics` SHALL be served by the OTel Prometheus exporter.

Metric names SHALL follow `app_<feature>_<noun>_<unit>` (e.g. `app_auth_logins_total`, `app_outbox_pending_gauge`). Label keys SHALL be drawn from a documented closed set per instrument; user identifiers and path-templated values MUST NOT appear as label keys.

#### Scenario: Feature obtains a meter via the factory

- **GIVEN** the authentication feature needs a counter
- **WHEN** it calls `get_app_meter("auth").create_counter("app_auth_logins_total")`
- **THEN** the instrument is registered against the application `MeterProvider`
- **AND** `/metrics` exposes it under the expected name

### Requirement: Initial domain metric set is live

The following metrics SHALL be declared and fed by exactly one production call site each:

- `app_auth_logins_total{result}` — counter; `result ∈ {success, failure}`; incremented by `LoginUser`.
- `app_auth_refresh_total{result}` — counter; `result ∈ {success, failure}`; incremented by the refresh-token rotation use case.
- `app_outbox_dispatched_total{result}` — counter; `result ∈ {success, failure}`; incremented per row by `DispatchPending`.
- `app_outbox_pending_gauge` — observable gauge fed by a per-tick `COUNT(*) WHERE status='pending'`.
- `app_jobs_enqueued_total{handler}` — counter incremented in every `JobQueuePort.enqueue` adapter; `handler` is a registered handler name.

Additionally, four SQLAlchemy pool gauges SHALL be registered as observable callbacks against the engine pool: `app_db_pool_checked_in`, `app_db_pool_checked_out`, `app_db_pool_overflow`, `app_db_pool_size`.

The test suite SHALL contain at least one unit test per metric asserting it increments / updates from its intended call site, and a regression test that the published metric-name set matches the documented catalog.

#### Scenario: Successful login increments the success counter

- **GIVEN** a registered user
- **WHEN** the user logs in successfully
- **THEN** `app_auth_logins_total{result="success"}` increases by exactly 1
- **AND** `app_auth_logins_total{result="failure"}` is unchanged

#### Scenario: Failed login increments the failure counter

- **GIVEN** a registered user
- **WHEN** the user submits a wrong password
- **THEN** `app_auth_logins_total{result="failure"}` increases by exactly 1

#### Scenario: Outbox dispatch updates both depth and totals

- **GIVEN** three pending outbox rows
- **WHEN** a relay tick dispatches them all successfully
- **THEN** `app_outbox_dispatched_total{result="success"}` increases by 3
- **AND** the next scrape reports `app_outbox_pending_gauge == 0`

#### Scenario: Job enqueue increments the per-handler counter

- **GIVEN** a registered job handler `send_email`
- **WHEN** the adapter enqueues a payload for that handler
- **THEN** `app_jobs_enqueued_total{handler="send_email"}` increases by exactly 1

#### Scenario: DB pool gauges reflect engine state

- **GIVEN** a checked-out connection from the engine pool
- **WHEN** `/metrics` is scraped
- **THEN** `app_db_pool_checked_out` is at least 1
- **AND** `app_db_pool_checked_in + app_db_pool_checked_out <= app_db_pool_size + app_db_pool_overflow`

#### Scenario: Disallowed label key is rejected

- **GIVEN** a contributor adds a counter with a `user_id` label key
- **WHEN** the cardinality regression test runs
- **THEN** it fails, naming `user_id` as outside the documented closed set

#### Scenario: Outbox pending callback survives a slow query

- **GIVEN** the `app_outbox_pending_gauge` observable callback hits the 2 s `statement_timeout` for `SELECT COUNT(*)`
- **WHEN** `/metrics` is scraped
- **THEN** the response still returns within the scrape budget
- **AND** the gauge value is the last successful observation (or absent for the tick), not a partial / hung sample

#### Scenario: Direct prometheus_client usage is rejected

- **GIVEN** a new feature module that imports `prometheus_client`
- **WHEN** quality gates run
- **THEN** the import-policy check fails, citing the OTel meter factory as the required entry point
