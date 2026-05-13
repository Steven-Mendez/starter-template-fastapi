## Context

Counters and histograms shipped in `metrics.py` are dead code unless someone calls them. We have a few already declared and a handful more operators would want. This proposal wires them through OpenTelemetry meters (not raw `prometheus_client`) and exposes them on `/metrics` via the OTel Prometheus exporter, so the same SDK/exporter wiring serves both traces and metrics.

## Decisions

- **OpenTelemetry meters, not raw `prometheus_client`**: gives us a vendor-neutral surface, lets the project swap exporters (Prometheus today, OTLP later) without touching call sites, and shares config with `improve-otel-instrumentation`. The Prometheus exporter remains the wire format on `/metrics`.
- **`Meter` factory**: features call `get_app_meter("auth")` rather than `metrics.get_meter("auth")` directly so we can centralize naming, sampling defaults, and test isolation.
- **Naming**: `app_<feature>_<noun>_<unit>`. The `app_` prefix avoids collision with auto-instrumentation. `_total` for monotonic counters, `_gauge` for gauges, `_seconds` for durations. Bounded label cardinality (no user ids, no path templates).
- **Initial set is closed**: this change ships exactly five domain instruments plus the SQLAlchemy pool gauges. New metrics arrive via the factory in subsequent changes.
- **Outbox depth as observable gauge**: the dispatch loop already does a per-tick COUNT for back-pressure; we attach the observable callback to that COUNT rather than maintaining a separate scrape collector.

## Risks / Trade-offs

- **Risk**: cardinality. All labels are closed sets (`result`, `handler` — `handler` is bounded by the `JobHandlerRegistry`). No user-id or path-templated labels.
- **Risk**: dual export paths (`prometheus_client` legacy globals + OTel meter) during migration. Mitigation: the old globals in `metrics.py` are deleted in this change; no parallel path.
- **Trade-off**: each instrumented call adds a few microseconds. Negligible compared to argon2 / DB I/O.

## Non-goals

- Replacing Prometheus as the exposition format. The OTel SDK is the producer; the Prometheus exporter remains the wire format on `/metrics`.
- Defining SLO targets / alert rules. We expose the signals; PromQL rules and dashboards land separately.
- Per-tenant or per-user-id metric cardinality. Closed-set labels only; user-scoped breakdowns belong in traces or logs.
- Exhaustive coverage of every use case. This change ships exactly five domain instruments plus the four pool gauges; new metrics arrive via the factory in subsequent changes.
- Auto-instrumentation library churn. Auto-instrumented metrics (HTTP duration, SQL duration) are out of scope and tracked by `improve-otel-instrumentation`.

## Migration

Single PR. Rollback safe — additive plus the deletion of two unused globals. Dashboards (if any) referencing the old metric names need to be updated; none exist in-repo today.
