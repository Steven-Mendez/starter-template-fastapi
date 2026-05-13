## ADDED Requirements

### Requirement: Unhandled exceptions route through an `ErrorReporterPort`

The application SHALL expose `ErrorReporterPort.capture(exc, **context)` and SHALL route every unhandled exception through it from `unhandled_exception_handler`. The shipped adapters are `LoggingErrorReporter` (default) and `SentryErrorReporter` (active when `APP_SENTRY_DSN` is set and `sentry-sdk` is importable). The context SHALL include at least `request_id`, `path`, `method`, and `principal_id` (nullable).

#### Scenario: Unhandled exception is captured

- **GIVEN** a fake `ErrorReporterPort` wired in tests
- **WHEN** a route raises an unexpected exception
- **THEN** the fake's `capture` was called exactly once with the raised exception
- **AND** the structured context includes the `request_id` from `RequestContextMiddleware`
- **AND** the structured context includes `path`, `method`, and `principal_id` keys

#### Scenario: Mapped 4xx errors are not reported

- **GIVEN** a fake `ErrorReporterPort` wired in tests
- **WHEN** a route returns a mapped 4xx Problem Details response (e.g. `InvalidCredentialsError` → 401)
- **THEN** the fake's `capture` was not called
- **AND** the 4xx response is still produced

### Requirement: Reporter selection is deterministic at startup

The factory SHALL select the reporter using the following rule and SHALL emit a startup log line naming the chosen reporter:

1. `APP_SENTRY_DSN` set AND `sentry_sdk` importable → `SentryErrorReporter`.
2. `APP_SENTRY_DSN` set AND `sentry_sdk` NOT importable → `LoggingErrorReporter` plus a WARN log line naming the missing optional extra (`pip install '.[sentry]'`).
3. `APP_SENTRY_DSN` unset → `LoggingErrorReporter` plus an INFO log line.

#### Scenario: No DSN, no Sentry — falls back cleanly

- **GIVEN** `APP_SENTRY_DSN` unset
- **WHEN** the application starts
- **THEN** `app.state.error_reporter` is a `LoggingErrorReporter`
- **AND** an INFO log line announces the chosen reporter

#### Scenario: DSN set but sentry_sdk missing — degrades to logging

- **GIVEN** `APP_SENTRY_DSN` set
- **AND** `sentry_sdk` is not importable
- **WHEN** the application starts
- **THEN** `app.state.error_reporter` is a `LoggingErrorReporter`
- **AND** a WARN log line names the missing `sentry` extra

#### Scenario: DSN set and sentry_sdk importable — uses Sentry

- **GIVEN** `APP_SENTRY_DSN` set
- **AND** `sentry_sdk` is importable
- **WHEN** the application starts
- **THEN** `app.state.error_reporter` is a `SentryErrorReporter`
- **AND** `sentry_sdk.init` was called with the configured DSN, environment, release, and `traces_sample_rate` from `APP_OTEL_TRACES_SAMPLER_RATIO`

### Requirement: Reporter failure never escalates the request failure

`ErrorReporterPort.capture` SHALL never raise. Adapter implementations SHALL wrap their work in `try/except Exception`, log the failure, and return.

#### Scenario: A broken reporter does not double-fault the request

- **GIVEN** an `ErrorReporterPort` whose `capture` raises internally
- **WHEN** a route raises an unhandled exception and the handler invokes the reporter
- **THEN** the original 500 response is still produced
- **AND** no second exception escapes `unhandled_exception_handler`
