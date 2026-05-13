## 1. Meter factory and SDK wiring

- [ ] 1.1a Delete the `AUTH_LOGIN_ATTEMPTS` and `AUTH_RATE_LIMIT_BLOCKS` `prometheus_client.Counter` globals in `src/app_platform/observability/metrics.py` (currently lines 33-43).
- [ ] 1.1b In the same file, build an OTel `MeterProvider` wired to `PrometheusMetricReader` from `opentelemetry-exporter-prometheus`; hold it module-level (`_METER_PROVIDER`) and call `metrics.set_meter_provider(...)`.
- [ ] 1.2 Add `get_app_meter(feature: str) -> Meter` in `src/app_platform/observability/metrics.py`. Features call this; they do NOT call `opentelemetry.metrics.get_meter` directly.
- [ ] 1.3 Add `opentelemetry-exporter-prometheus` to `pyproject.toml` `[project.dependencies]`.
- [ ] 1.4 In `src/app_platform/api/app_factory.py` (currently `configure_metrics(app, enabled=settings.metrics_enabled)` at line 95), replace the `prometheus_fastapi_instrumentator` mount with a mount of `prometheus_client.exposition.make_asgi_app()` bound to the OTel reader's registry on `/metrics`.

## 2. Initial domain metrics

- [ ] 2.1a Declare `app_auth_logins_total{result}` counter in `src/app_platform/observability/metrics.py` via the meter factory.
- [ ] 2.1b In `src/features/authentication/application/use_cases/auth/login_user.py`, increment exactly once per call with `result="success"` on the Ok branch and `result="failure"` on every Err branch.
- [ ] 2.2a Declare `app_auth_refresh_total{result}` counter in `src/app_platform/observability/metrics.py`.
- [ ] 2.2b Wire it from `src/features/authentication/application/use_cases/auth/rotate_refresh_token.py` (the refresh-token rotation use case) — one increment per call.
- [ ] 2.3a Declare `app_outbox_dispatched_total{result}` counter in `src/app_platform/observability/metrics.py`.
- [ ] 2.3b Wire it from `src/features/outbox/application/use_cases/dispatch_pending.py` — one increment per row dispatched, after the per-row commit.
- [ ] 2.4a Declare `app_outbox_pending_gauge` as an OTel observable gauge in `src/app_platform/observability/metrics.py`, registered with a callback bound at composition time (`src/main.py`) once the engine exists.
- [ ] 2.4b The callback executes `SELECT COUNT(*) FROM outbox_messages WHERE status='pending'` against the engine with `SET LOCAL statement_timeout='2s'` (Postgres) to protect the scrape path from a slow DB.
- [ ] 2.5a Declare `app_jobs_enqueued_total{handler}` counter in `src/app_platform/observability/metrics.py`.
- [ ] 2.5b Increment it from `src/features/background_jobs/adapters/outbound/in_process/adapter.py::enqueue` and `src/features/background_jobs/adapters/outbound/arq/adapter.py::enqueue`.

## 3. SQLAlchemy pool gauges

- [ ] 3.1 Declare observable gauges `app_db_pool_checked_in`, `app_db_pool_checked_out`, `app_db_pool_overflow`, `app_db_pool_size`. Register their callbacks against the engine's pool. Bound once at composition time.

## 4. Tests

- [ ] 4.1 Unit: each instrumented call site increments / updates its metric. Use an in-memory `MetricReader` for assertions.
- [ ] 4.2 Unit: assert the metric name set on `/metrics` matches the documented catalog exactly (no extras, no missing).
- [ ] 4.3 Integration (Postgres): dispatch N rows → observable gauge returns 0 after the tick; `app_outbox_dispatched_total{result="success"}` increases by N.
- [ ] 4.4 Cardinality regression: assert label keys on every counter are limited to the documented closed set.

## 5. Docs

- [ ] 5.1 Update `docs/observability.md` with the metric catalog, naming convention (`app_<feature>_<noun>_<unit>`), and the `get_app_meter(feature)` factory contract.
- [ ] 5.2 `make ci` green.
