## Why

`src/app_platform/observability/metrics.py` declares `AUTH_LOGIN_ATTEMPTS` and `AUTH_RATE_LIMIT_BLOCKS` counters, but `grep -rn` finds zero call sites — `/metrics` exposes them as flat zeros forever. There are also no metrics for outbox depth, relay lag, JWT issuance, queue depth, or DB pool stats — the very signals operators need to alert on. The instrumentation surface is *present* but *unused*.

The existing surface is `prometheus_client` Counters declared as module globals. We're migrating to **OpenTelemetry meters** so metrics share the same SDK / exporter pipeline as traces, and so adapters (Prometheus exporter, OTLP exporter) are swappable at composition time. A small `Meter` factory in `app_platform/observability/metrics.py` is the only place features touch the SDK.

## What Changes

- Use OpenTelemetry meters (`opentelemetry.metrics.get_meter(...)`) — **not** the raw `prometheus_client` API. The Prometheus exporter remains the default scrape target via `opentelemetry-exporter-prometheus`.
- Metric naming convention: `app_<feature>_<noun>_<unit>` (e.g. `app_auth_logins_total`, `app_outbox_pending_gauge`). Label sets bounded; no user-id or path-templated cardinality.
- Initial metric set (each fed by exactly one production call site):
  - `app_auth_logins_total{result}` — counter; `result ∈ {success, failure}`.
  - `app_auth_refresh_total{result}` — counter; `result ∈ {success, failure}` (refresh-token rotation outcome).
  - `app_outbox_dispatched_total{result}` — counter; `result ∈ {success, failure}`.
  - `app_outbox_pending_gauge` — observable gauge; set per relay tick from a cheap `COUNT(*) WHERE status='pending'`.
  - `app_jobs_enqueued_total{handler}` — counter; `handler` is the registered handler name (bounded by the `JobHandlerRegistry`).
- Implementers add new metrics through a `Meter` factory exported from `app_platform/observability/metrics.py` (`get_app_meter(feature: str) -> Meter`). Features import the factory; they do NOT call `opentelemetry.metrics.get_meter` directly.
- Register a SQLAlchemy pool observable-gauge set (`app_db_pool_checked_in`, `app_db_pool_checked_out`, `app_db_pool_overflow`, `app_db_pool_size`) as observable callbacks against the engine's pool. Bound at composition time.

**Capabilities — Modified**: `project-layout` (observability metrics surface).

## Impact

- **Code**:
  - `src/app_platform/observability/metrics.py` — replace the `prometheus_client` globals with the `Meter` factory; declare the five initial instruments; register the SQLAlchemy pool observable gauges.
  - `src/app_platform/api/app_factory.py` — wire the Prometheus exporter / `/metrics` route through the OTel `MeterProvider`.
  - `src/features/authentication/application/use_cases/auth/login_user.py` — increment `app_auth_logins_total{result}`.
  - `src/features/authentication/application/use_cases/auth/refresh_token.py` — increment `app_auth_refresh_total{result}`.
  - `src/features/outbox/application/use_cases/dispatch_pending.py` — increment `app_outbox_dispatched_total{result}` per row; register the pending-count observable callback.
  - `src/features/background_jobs/adapters/outbound/in_process/adapter.py` and `.../arq/adapter.py` — increment `app_jobs_enqueued_total{handler}` in `enqueue(...)`.
  - `pyproject.toml` — add `opentelemetry-api`, `opentelemetry-sdk` (already present), `opentelemetry-exporter-prometheus`.
- **Tests**: per-metric unit tests under `src/app_platform/tests/unit/observability/test_metrics.py` and feature-local tests (one per call site). Integration test asserts `outbox_pending_gauge` drops to 0 after a relay tick.
- **Docs**: `docs/observability.md` — metric catalog, naming convention, `Meter` factory usage.

## Depends on

- None hard. Best paired with `improve-otel-instrumentation` (shares the OTel SDK init in `tracing.py` / `metrics.py`).

## Conflicts with

- `improve-otel-instrumentation` — shares `LoginUser` and `DispatchPending` call sites; both touch the OTel SDK init. Land together or sequence carefully.
- `harden-auth-defense-in-depth`, `make-auth-flows-transactional` — share `LoginUser` / `RefreshToken`.
- `fix-outbox-dispatch-idempotency`, `propagate-trace-context-through-jobs`, `redact-pii-and-tokens-in-logs` — share `dispatch_pending.py`.
- `add-error-reporting-seam`, `harden-http-middleware-stack`, `harden-rate-limiting` — share `app_factory.py`.
