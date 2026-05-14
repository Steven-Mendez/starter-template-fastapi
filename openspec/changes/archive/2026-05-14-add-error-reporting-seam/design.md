## Depends on

(none) — this change is independent of the errors-http taxonomy chain. The reporter receives `BaseException` values, so it works whether or not `align-error-class-hierarchy` has landed.

## Conflicts with

Shares `src/app_platform/api/error_handlers.py` with `align-error-class-hierarchy`, `add-stable-problem-types`, `enrich-validation-error-payload`, `declare-error-responses-in-openapi`, `preserve-error-response-headers`. The chain merge order is `align-error-class-hierarchy → add-stable-problem-types → enrich-validation-error-payload → declare-error-responses-in-openapi → preserve-error-response-headers`. This change can land at any point in or after that chain; rebase against the latest tip and re-resolve the single edit site (`unhandled_exception_handler`).

Shares `src/app_platform/api/app_factory.py` with `harden-http-middleware-stack`, `harden-rate-limiting`, `expose-domain-metrics` — separate sections of the factory; resolve by ordering the `create_app` body.

Shares `src/app_platform/config/settings.py` with `fix-bootstrap-admin-escalation`, `strengthen-production-validators`, `harden-rate-limiting` — additive only; rebase the settings model.

Shares `pyproject.toml` (optional `sentry` extra) with `enable-strict-mypy`, `expand-ruff-ruleset`, `harden-ci-security`, `trim-runtime-deps`, `clean-architecture-seams` — additive only.

## Context

Paging on exceptions is a Day-1 operational need; templates that don't have a slot for it leave operators bolting in `sentry_sdk` calls ad hoc. The right shape is a port + two adapters: logging (default) and Sentry (optional). Operators pick at deploy time via env var.

## Decisions

- **Port + adapters, not a direct `sentry_sdk.init(...)` call**: matches the rest of the codebase (every external is a port). Lets test code substitute a fake recorder without monkeypatching `sentry_sdk`.
- **Reporter selection rule** (resolved):
  1. If `APP_SENTRY_DSN` is set AND `sentry_sdk` is importable → wire `SentryErrorReporter`.
  2. If `APP_SENTRY_DSN` is set AND `sentry_sdk` is NOT importable → wire `LoggingErrorReporter`, emit a WARN log at startup naming the missing extra (`pip install '.[sentry]'`), and continue.
  3. If `APP_SENTRY_DSN` is unset → wire `LoggingErrorReporter` and emit an INFO log naming the chosen reporter.
- **Optional extra `[project.optional-dependencies] sentry = [...]`**: Sentry is a substantial dep; teams not using it don't ship it.
- **No DSN refusal in `validate_production`**: this is a paging concern, not a safety one. Operators on internal-only deployments may legitimately not have paging. The startup INFO/WARN log surfaces the chosen reporter loudly enough for ops monitoring.
- **`traces_sample_rate` ties to `APP_OTEL_TRACES_SAMPLER_RATIO`** (introduced by `improve-otel-instrumentation`). Until that change lands, fall back to `1.0` in non-production and `0.1` in production — same defaults that change will codify.
- **Context shape passed to `capture`**: `request_id: str`, `path: str`, `method: str`, `principal_id: str | None`. Rationale: minimum useful debugging context; matches `RequestContextMiddleware` outputs.

## Risks / Trade-offs

- **Risk**: forgotten DSN in prod → no paging. Mitigation: the startup log line says "error reporter: <kind>" loudly enough that ops can see it.
- **Risk**: Sentry adapter swallows exceptions during `capture`. Mitigation: the port wraps `capture` in a `try/except` that logs to the standard logger and never re-raises.

## Non-goals

- Shipping a second optional reporter (Honeybadger, Rollbar, Datadog APM). The port makes addition trivial; this change ships only the two adapters above.
- Capturing handled `ApplicationError` results — only unhandled exceptions route through the reporter; mapped 4xx responses do not.
- Refusing startup when `APP_SENTRY_DSN` is unset in production. Paging is an operator choice, not a safety invariant.
- Sampling, scrubbing, or transport configuration beyond `dsn`, `environment`, `release`, `traces_sample_rate`. Operators tune those via Sentry's own config.

## Migration

Single PR. Rollback: revert.
