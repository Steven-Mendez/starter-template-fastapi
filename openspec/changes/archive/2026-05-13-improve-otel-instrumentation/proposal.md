## Why

Two OTel-tooling gaps:

1. **Sampler is `ParentBased(AlwaysOn)`** (the default). Under load this emits one span per DB query for every request, overwhelms the collector, and the default `BatchSpanProcessor` (`max_queue=2048`) silently drops spans on burst. There is no `OTEL_TRACES_SAMPLER_RATIO` knob.
2. **No use-case-level spans or attributes.** Auto-instrumentation today covers only the FastAPI inbound path; SQLAlchemy/httpx/Redis client spans are not enabled, and use cases like `LoginUser`, `BootstrapSystemAdmin`, `DispatchPending` have no manual spans with `user.id`, `outbox.message_id`, `authz.action`, or `job.name` attributes. Operators see HTTP duration but cannot distinguish slow argon2 verify from slow DB.

## What Changes

- Add `APP_OTEL_TRACES_SAMPLER_RATIO` (default `1.0` in dev/test, recommend `0.1` in production) and wire it into the `TracerProvider` sampler. Bump `BatchSpanProcessor` queue size to `8192` (`max_export_batch_size=512`). Document head-vs-tail trade-off in `docs/observability.md`.
- Enable the following auto-instrumentations explicitly in `tracing.py`, each gated by an env toggle (default `true`):
  - `opentelemetry-instrumentation-sqlalchemy` — `APP_OTEL_INSTRUMENT_SQLALCHEMY` (always on; SQL spans).
  - `opentelemetry-instrumentation-httpx` — `APP_OTEL_INSTRUMENT_HTTPX` (Resend adapter, future outbound HTTP).
  - `opentelemetry-instrumentation-redis` — `APP_OTEL_INSTRUMENT_REDIS` (only loaded when `APP_AUTH_REDIS_URL` or `APP_JOBS_REDIS_URL` is set).
- Add a small `@traced("use_case.name", attrs={...})` decorator in `app_platform/observability/tracing.py`. Apply it to `LoginUser`, `RegisterUser`, `BootstrapSystemAdmin`, `DispatchPending`, the rate-limit dependency, and the per-row outbox dispatch path. Attach `user.id`, `outbox.message_id`, `authz.action`, `job.name` as appropriate. PII (raw email, raw token) MUST NOT appear in attributes; use `user.email_hash`.

**Capabilities — Modified**: `project-layout`.

## Impact

- **Code**:
  - `src/app_platform/observability/tracing.py` (sampler, processor, auto-instrumentation toggles, `@traced` decorator).
  - `src/app_platform/config/sub_settings.py` (`ObservabilitySettings`: `otel_traces_sampler_ratio`, `otel_instrument_sqlalchemy`, `otel_instrument_httpx`, `otel_instrument_redis`).
  - `src/features/authentication/application/use_cases/auth/login_user.py`, `register_user.py` — decorator applied.
  - `src/features/authorization/application/use_cases/bootstrap_system_admin.py` — decorator applied.
  - `src/features/outbox/application/use_cases/dispatch_pending.py` — decorator applied, per-row span.
  - `src/features/authentication/adapters/inbound/http/auth.py` (rate-limit dep) — decorator applied.
- **Tests**: unit assertions using `opentelemetry.sdk.trace.export.in_memory_span_exporter.InMemorySpanExporter`; new tests under `src/app_platform/tests/unit/observability/test_tracing.py`.
- **Docs**: `docs/observability.md` — sampler ratio guidance, instrumentation toggles, head- vs tail-based trade-off.
- **Deps**: `pyproject.toml` adds `opentelemetry-instrumentation-sqlalchemy`, `opentelemetry-instrumentation-httpx`, `opentelemetry-instrumentation-redis`.

## Depends on

- None hard. Should land before `propagate-trace-context-through-jobs` (consumes the sampler + decorator infrastructure) and before `add-error-reporting-seam` (Sentry `traces_sample_rate` reuses `APP_OTEL_TRACES_SAMPLER_RATIO`).

## Conflicts with

- `add-error-reporting-seam` — references `APP_OTEL_TRACES_SAMPLER_RATIO`; both must agree on the env-var name and default.
- `propagate-trace-context-through-jobs` — both touch `tracing.py` (propagator config) and `dispatch_pending.py` (per-row span); land this change first.
- `harden-auth-defense-in-depth`, `make-auth-flows-transactional`, `expose-domain-metrics` — share `LoginUser` / `RegisterUser` / `DispatchPending`; coordinate ordering.
- `fix-outbox-dispatch-idempotency` — shares `DispatchPending`; coordinate.
