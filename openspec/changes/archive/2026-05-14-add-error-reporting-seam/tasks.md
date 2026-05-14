## 1. Port + adapters

- [x] 1.1 Create `src/app_platform/observability/error_reporter.py` and declare `class ErrorReporterPort(Protocol)` with `def capture(self, exc: BaseException, **context: Any) -> None`.
- [x] 1.2 Implement `class LoggingErrorReporter` in the same module — emits a structured WARN log line with the exception class, message, and `**context` keys, and returns.
- [x] 1.3 Implement `class SentryErrorReporter` in the same module — wraps `sentry_sdk.capture_exception(exc)` and `sentry_sdk.set_context(...)`; lives behind the `sentry` optional extra; on `ImportError` of `sentry_sdk`, raises `ModuleNotFoundError` at construction time so the factory falls back per the selection rule.
- [x] 1.4 Wrap `capture` in `try/except Exception` that logs and never re-raises (so a broken reporter never escalates the request failure).

## 2. Settings

- [x] 2.1 Add to `src/app_platform/config/settings.py`: `app_sentry_dsn: SecretStr | None = None`, `app_sentry_environment: str | None = None`, `app_sentry_release: str | None = None`. Env vars: `APP_SENTRY_DSN`, `APP_SENTRY_ENVIRONMENT`, `APP_SENTRY_RELEASE`.
- [x] 2.2 In `AppSettings.validate_production`, allow DSN-unset; emit no error. (Paging is an operator choice, not a refusal.)

## 3. Wiring

- [x] 3.1 In `create_app` (`src/app_platform/api/app_factory.py`), choose the reporter per `design.md` selection rule: DSN set + `sentry_sdk` importable → `SentryErrorReporter`; DSN set + `sentry_sdk` missing → `LoggingErrorReporter` plus WARN log naming the missing extra; DSN unset → `LoggingErrorReporter` plus INFO log.
- [x] 3.2 Bind the chosen reporter on `app.state.error_reporter`.
- [x] 3.3 In `unhandled_exception_handler` (`src/app_platform/api/error_handlers.py`), retrieve the reporter from `request.app.state.error_reporter` and call `reporter.capture(exc, request_id=request_id, path=str(request.url.path), method=request.method, principal_id=getattr(request.state, "principal_id", None))`.
- [x] 3.4 In `create_app`, when DSN is set, call `sentry_sdk.init(dsn=settings.app_sentry_dsn.get_secret_value(), environment=settings.app_sentry_environment, release=settings.app_sentry_release, traces_sample_rate=settings.observability.otel_traces_sampler_ratio)`.

## 4. Optional extra

- [x] 4.1 In `pyproject.toml`, add `[project.optional-dependencies] sentry = ["sentry-sdk[fastapi]>=2"]`.

## 5. Tests

- [x] 5.1 Add a unit test that wires a fake `ErrorReporterPort`, raises inside a route, and asserts `capture` was called exactly once with the raised exception and a `request_id` in context.
- [x] 5.2 Add a unit test that asserts, with no DSN, the wired reporter is `LoggingErrorReporter` and the startup log line names it.
- [x] 5.3 Add a unit test that asserts, with DSN set but `sentry_sdk` not importable (monkeypatched), the factory falls back to `LoggingErrorReporter` and emits a WARN log naming the missing extra.

## 6. Docs

- [x] 6.1 Add a "Error reporting" section to `docs/observability.md` covering reporter selection, the `APP_SENTRY_*` env vars, and how to swap reporter implementations in tests.

## 7. Wrap-up

- [x] 7.1 Run `make ci` and confirm green.
