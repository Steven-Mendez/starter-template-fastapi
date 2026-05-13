## ADDED Requirements

### Requirement: OTel sampling is configurable

The application SHALL configure the `TracerProvider` with `ParentBased(TraceIdRatioBased(ratio))` where `ratio` is sourced from `APP_OTEL_TRACES_SAMPLER_RATIO` (default `1.0`). `BatchSpanProcessor` SHALL be configured with `max_queue_size=8192` and `max_export_batch_size=512`. When `APP_ENVIRONMENT=production` and ratio is `1.0`, `configure_tracing` SHALL emit a warning-level log (NOT a refusal) recommending a value below `1.0`. This is the only "warn but don't refuse" path in the codebase; the `validate(errors)` and `validate_production(errors)` settings methods continue to refuse on hard misconfigurations.

#### Scenario: Ratio applied to sampler

- **GIVEN** `APP_OTEL_TRACES_SAMPLER_RATIO=0.25`
- **WHEN** the `TracerProvider` is built
- **THEN** its sampler is `ParentBased(TraceIdRatioBased(0.25))`

#### Scenario: Ratio 1.0 in production warns

- **GIVEN** `APP_ENVIRONMENT=production` and `APP_OTEL_TRACES_SAMPLER_RATIO=1.0`
- **WHEN** the settings validator runs at startup
- **THEN** a warning-level log entry is emitted recommending a lower ratio
- **AND** startup is NOT refused

### Requirement: Auto-instrumentation libraries are enabled

The application SHALL register the following OpenTelemetry auto-instrumentations during tracing setup, each gated by a settings toggle defaulted to `true`:

- `SQLAlchemyInstrumentor` — gated by `APP_OTEL_INSTRUMENT_SQLALCHEMY`.
- `HTTPXClientInstrumentor` — gated by `APP_OTEL_INSTRUMENT_HTTPX`.
- `RedisInstrumentor` — gated by `APP_OTEL_INSTRUMENT_REDIS`; skipped entirely when no Redis URL is configured.

The FastAPI auto-instrumentation that already runs SHALL remain unchanged.

#### Scenario: SQLAlchemy queries emit spans by default

- **GIVEN** `APP_OTEL_INSTRUMENT_SQLALCHEMY=true` (the default)
- **WHEN** a request executes a SQL statement
- **THEN** the captured trace contains a span whose name begins with the SQL verb (e.g. `SELECT`)

#### Scenario: Redis instrumentation skipped when no Redis URL

- **GIVEN** neither `APP_AUTH_REDIS_URL` nor `APP_JOBS_REDIS_URL` is set
- **WHEN** the application starts
- **THEN** `RedisInstrumentor` is not invoked

#### Scenario: Toggle off disables the instrumentor

- **GIVEN** `APP_OTEL_INSTRUMENT_HTTPX=false`
- **WHEN** the application starts and an outbound `httpx` call is made
- **THEN** no `httpx`-named span is emitted
- **AND** `HTTPXClientInstrumentor().instrument()` was never invoked

#### Scenario: Sampler ratio out of range refuses startup

- **GIVEN** `APP_OTEL_TRACES_SAMPLER_RATIO=1.5`
- **WHEN** the settings validator runs at startup
- **THEN** startup is refused with an error citing the `0.0 <= ratio <= 1.0` bound

### Requirement: Hot-path application use cases are individually traced

The following use cases SHALL be wrapped with the `@traced(name, attrs)` decorator (or an equivalent inline span) at the listed span names: `LoginUser → auth.login_user`, `RegisterUser → auth.register_user`, `BootstrapSystemAdmin → authz.bootstrap_system_admin`, `DispatchPending → outbox.dispatch_pending`, the rate-limit dependency → `auth.rate_limit`. Other use cases MAY be decorated; this requirement is the floor, not the ceiling.

Attributes SHALL include relevant domain identifiers (`user.id`, `outbox.message_id`, `outbox.handler`, `job.name`, `outbox.batch_size`) and MUST NOT include raw PII; email addresses SHALL appear only as `user.email_hash`.

On raised exception the decorator SHALL call `record_exception(...)`, set the span status to `ERROR`, and re-raise.

#### Scenario: Login produces a use-case-level span

- **GIVEN** an in-memory span exporter
- **WHEN** `LoginUser.execute(...)` completes successfully
- **THEN** the exporter records a span named `auth.login_user`
- **AND** the span has at least one attribute (e.g. `user.email_hash`)
- **AND** the span does NOT contain the raw email anywhere in its attributes

#### Scenario: Per-row outbox dispatch produces a child span

- **GIVEN** a relay tick dispatching three pending rows
- **WHEN** the tick finishes
- **THEN** the exporter records one parent `outbox.dispatch_pending` span
- **AND** three child spans each carrying `outbox.message_id` and `outbox.handler`

#### Scenario: Decorator re-raises and records exception

- **GIVEN** a decorated use case that raises `ValueError`
- **WHEN** it is invoked
- **THEN** the span has status `ERROR`
- **AND** the exception event is attached to the span
- **AND** the caller observes the original `ValueError`

#### Scenario: Raw email is never used as a span attribute

- **GIVEN** a `LoginUser` call with email `alice@example.com`
- **WHEN** the captured spans are inspected
- **THEN** no attribute value across any captured span equals `alice@example.com`
- **AND** the `user.email_hash` attribute is present on the `auth.login_user` span
