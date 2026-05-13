## 1. Sampler + processor configuration

- [x] 1.1 Add `otel_traces_sampler_ratio: float = 1.0` to `ObservabilitySettings` (env `APP_OTEL_TRACES_SAMPLER_RATIO`). Validate `0.0 <= ratio <= 1.0` in the standard `validate(errors)` method.
- [x] 1.2 In `src/app_platform/observability/tracing.py:73`, change `provider = TracerProvider(resource=resource)` to `provider = TracerProvider(resource=resource, sampler=ParentBased(TraceIdRatioBased(settings.otel_traces_sampler_ratio)))`. Import the samplers from `opentelemetry.sdk.trace.sampling`.
- [x] 1.3 Override `BatchSpanProcessor(..., max_queue_size=8192, max_export_batch_size=512)` at line 80.
- [x] 1.4 In `configure_tracing` (NOT in `validate_production`, since the rest of `validate_production` refuses, not warns), emit a `_logger.warning(...)` line at startup when `settings.environment == "production"` and `otel_traces_sampler_ratio == 1.0`. Document this as the only "warn but don't refuse" path in the codebase.

## 2. Auto-instrumentation toggles

- [x] 2.1 Add `otel_instrument_sqlalchemy: bool = True`, `otel_instrument_httpx: bool = True`, `otel_instrument_redis: bool = True` to `ObservabilitySettings`.
- [x] 2.2a In `src/app_platform/observability/tracing.py`, wrap the existing `SQLAlchemyInstrumentor().instrument()` call (currently line 87 inside `configure_tracing`) in `if settings.otel_instrument_sqlalchemy:`.
- [x] 2.2b In the same function, add a `from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor` import (local, inside the function like the other instrumentors) and a `HTTPXClientInstrumentor().instrument()` block gated by `if settings.otel_instrument_httpx:`.
- [x] 2.2c Replace the existing Redis gate `if settings.auth_redis_url:` (currently line 89) with `if settings.otel_instrument_redis and (settings.auth_redis_url or settings.jobs_redis_url):` so the JOBS Redis URL also triggers instrumentation.
- [x] 2.3 (covered by 2.2) — the new gate skips the Redis instrumentor entirely when no Redis URL is configured.
- [x] 2.4 Add `opentelemetry-instrumentation-sqlalchemy`, `opentelemetry-instrumentation-httpx`, `opentelemetry-instrumentation-redis` to `pyproject.toml`. Note: `sqlalchemy` and `redis` instrumentation are already imported transitively but not declared as direct deps; declare them explicitly so Renovate manages versions.
- [x] 2.5 Expose `provider` as a module-level `_PROVIDER: TracerProvider | None` (paired with the existing `_TRACING_CONFIGURED` flag) so `add-graceful-shutdown` can call `_PROVIDER.shutdown()` from the lifespan finalizer. Provide a `def shutdown_tracing() -> None` helper in `tracing.py` that runs the shutdown idempotently.

## 3. `@traced` decorator

- [x] 3.1 Implement `@traced(name, attrs=None)` in `tracing.py` that starts a span around the wrapped callable; `attrs` may be a dict or `Callable[..., dict]`.
- [x] 3.2 On raised exception, call `record_exception` + `set_status(StatusCode.ERROR)` and re-raise (do not swallow).
- [x] 3.3 Provide an `async`-aware variant (or one decorator that detects coroutine functions).

## 4. Apply to use cases

- [x] 4.1 Decorate `LoginUser.execute` with `name="auth.login_user"`, attrs `{"user.email_hash": ...}` (no raw PII).
- [x] 4.2 Decorate `RegisterUser.execute` with `name="auth.register_user"`.
- [x] 4.3 Decorate `BootstrapSystemAdmin.execute` with `name="authz.bootstrap_system_admin"`.
- [x] 4.4 Decorate `DispatchPending.execute` with `name="outbox.dispatch_pending"`, attrs `{"outbox.batch_size": ...}`.
- [x] 4.5 Decorate the rate-limit dependency with `name="auth.rate_limit"`, attrs `{"rate_limit.key_hash": ...}`.
- [x] 4.6 Per-row dispatch in `DispatchPending`: wrap each row in a child span with attrs `{"outbox.message_id": ..., "outbox.handler": ...}`.

## 5. Tests

- [x] 5.1 Unit: install `InMemorySpanExporter`; assert decorated calls produce a span with expected name and attribute keys.
- [x] 5.2 Unit: raising the wrapped function records an `ERROR` status and re-raises.
- [x] 5.3 Unit: sampler ratio 0.0 produces zero non-parent spans; ratio 1.0 produces all spans.
- [x] 5.4 Unit: with `otel_instrument_redis=False` the Redis instrumentor is never invoked.

## 6. Docs

- [x] 6.1 Update `docs/observability.md`: sampling-ratio guidance, head- vs tail-based trade-off, exporter queue sizing, auto-instrumentation toggles.
- [x] 6.2 `make ci` green.
