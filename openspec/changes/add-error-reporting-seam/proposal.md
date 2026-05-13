## Why

`grep -rn 'sentry|honeybadger|rollbar'` returns nothing. The unhandled-exception handler in `src/app_platform/api/error_handlers.py` only emits a structured log line. A 5xx surge produces no paging signal beyond log-volume alerting — the team learns about outages on Slack instead of pager.

## What Changes

- Add an optional `sentry-sdk` extra (`[project.optional-dependencies] sentry = ["sentry-sdk[fastapi]>=2"]`).
- Add `APP_SENTRY_DSN`, `APP_SENTRY_ENVIRONMENT`, `APP_SENTRY_RELEASE` settings (all optional).
- In `create_app`, before `configure_tracing`, conditionally call `sentry_sdk.init(dsn=..., traces_sample_rate=...)` when DSN is set. Tie `traces_sample_rate` to `APP_OTEL_TRACES_SAMPLER_RATIO` so OTel and Sentry agree.
- In `unhandled_exception_handler`, retrieve the reporter from `app.state.error_reporter` and call `capture(exc, **context)` (no-op when DSN unset).
- Keep the seam pluggable: `ErrorReporterPort` Protocol with `capture(exc, **context)`; `SentryErrorReporter` adapter; default `LoggingErrorReporter` adapter.

**Capabilities — Modified**: `project-layout`.

## Impact

- **Code (new)**:
  - `src/app_platform/observability/error_reporter.py` (defines `ErrorReporterPort`, `LoggingErrorReporter`, `SentryErrorReporter`).
- **Code (edit)**:
  - `src/app_platform/api/error_handlers.py` (`unhandled_exception_handler` calls `app.state.error_reporter.capture(...)`).
  - `src/app_platform/api/app_factory.py` (selects the reporter at startup, binds it on `app.state.error_reporter`, emits a startup log line naming the chosen reporter).
  - `src/app_platform/config/settings.py` (adds `app_sentry_dsn: SecretStr | None = None`, `app_sentry_environment: str | None = None`, `app_sentry_release: str | None = None`).
  - `pyproject.toml` (adds `[project.optional-dependencies] sentry = ["sentry-sdk[fastapi]>=2"]`).
  - `docs/observability.md` (adds a section on error reporting and how to swap reporters).
- **Production**: paging works when DSN is set. No change when unset.
