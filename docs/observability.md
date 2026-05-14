# Observability Guide

This guide describes the service's built-in metrics, tracing, and structured
logs.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `APP_METRICS_ENABLED` | `true` | Exposes Prometheus metrics at `GET /metrics`. |
| `APP_OTEL_EXPORTER_ENDPOINT` | unset | Enables OpenTelemetry tracing and exports spans over OTLP/HTTP. |
| `APP_OTEL_SERVICE_NAME` | `starter-template-fastapi` | Service name attached to traces and JSON logs. |
| `APP_OTEL_SERVICE_VERSION` | `0.1.0` | Service version attached to traces and JSON logs. |
| `APP_OTEL_TRACES_SAMPLER_RATIO` | `1.0` | Head-based sampler ratio in `[0.0, 1.0]`. Set to `0.1` in production. |
| `APP_OTEL_INSTRUMENT_SQLALCHEMY` | `true` | Toggle SQLAlchemy auto-instrumentation. |
| `APP_OTEL_INSTRUMENT_HTTPX` | `true` | Toggle HTTPX auto-instrumentation. |
| `APP_OTEL_INSTRUMENT_REDIS` | `true` | Toggle Redis auto-instrumentation (only loaded when a Redis URL is set). |
| `APP_LOG_LEVEL` | `INFO` | Root Python log level used by the application. |

## Metrics

Prometheus metrics are exposed at:

```bash
curl -s http://localhost:8000/metrics
```

The endpoint is mounted only when `APP_METRICS_ENABLED=true`. Health and metrics
routes are excluded from HTTP request metrics to avoid probe noise.

Example Prometheus scrape config:

```yaml
scrape_configs:
  - job_name: starter-template-fastapi
    metrics_path: /metrics
    static_configs:
      - targets: ["api:8000"]
```

## Tracing

Tracing is opt-in. Set `APP_OTEL_EXPORTER_ENDPOINT` to an OTLP/HTTP trace
endpoint, for example an OpenTelemetry Collector, Tempo, or Jaeger endpoint:

```bash
export APP_OTEL_EXPORTER_ENDPOINT=http://otel-collector:4318/v1/traces
export APP_OTEL_SERVICE_NAME=starter-template-fastapi
export APP_OTEL_SERVICE_VERSION=0.1.0
```

When tracing is enabled, the app instruments:

- FastAPI requests.
- SQLAlchemy/SQLModel database calls (gated by `APP_OTEL_INSTRUMENT_SQLALCHEMY`).
- Outbound HTTPX calls (gated by `APP_OTEL_INSTRUMENT_HTTPX`).
- Redis calls when `APP_AUTH_REDIS_URL` or `APP_JOBS_REDIS_URL` is set
  (gated by `APP_OTEL_INSTRUMENT_REDIS`).

Health and metrics routes are excluded from FastAPI spans.

When `APP_OTEL_EXPORTER_ENDPOINT` is unset, tracing instrumentation is not
installed and OpenTelemetry stays on its default no-op provider.

### Sampling

Spans are sampled head-based at the root with
`ParentBased(TraceIdRatioBased(APP_OTEL_TRACES_SAMPLER_RATIO))`. The default
ratio is `1.0` (every trace is kept) — appropriate for development and tests
where individual traces are valuable.

In production, leave `APP_OTEL_TRACES_SAMPLER_RATIO` at `1.0` only if your
collector can absorb the volume; otherwise dial it down (e.g. `0.1`). The
process logs a warning when the ratio is `1.0` in production, but it does
NOT refuse to start: head-based sampling is a tuning knob, not a safety
gate. (This is the only "warn but don't refuse" path in the codebase; every
other production-misconfiguration check refuses startup.)

Head-based vs. tail-based: head-based sampling decides at trace start, so
all spans of a sampled trace are kept and all spans of a dropped trace are
discarded — cheap, but it cannot prioritize "interesting" traces (errors,
slow requests). Tail-based sampling — promoting interesting traces after
all spans land at the collector — is a collector-side feature (e.g. the
OTel Collector's `tail_sampling` processor); this service emits head-based
samples and lets the collector make the final call.

### Exporter queue sizing

`BatchSpanProcessor` is configured with `max_queue_size=8192` and
`max_export_batch_size=512`. These are bumped from the SDK defaults
(`2048` / `512`) so bursty traffic does not silently drop spans before the
collector catches up.

### Use-case spans

Hot-path use cases emit application-layer spans:

| Span name | Where | Notable attributes |
| --- | --- | --- |
| `auth.login_user` | `LoginUser.execute` | `user.email_hash` |
| `auth.register_user` | `RegisterUser.execute` | `user.email_hash` |
| `authz.bootstrap_system_admin` | `BootstrapSystemAdmin.execute` | — |
| `outbox.dispatch_pending` | `DispatchPending.execute` (relay tick) | `outbox.batch_size` |
| `outbox.dispatch_row` | per-row child of `outbox.dispatch_pending` | `outbox.message_id`, `outbox.handler` |
| `auth.rate_limit` | `_check_rate_limit` dependency | `rate_limit.key_hash` |

PII MUST NOT appear in span attributes. Email addresses are reduced to a
deterministic short hash (`user.email_hash` = `sha256(email)[:16]`); raw
emails, raw tokens, and passwords are never recorded. The `@traced`
decorator in `app_platform.observability.tracing` is the public seam for
adding new use-case spans.

## Logs

Development runs use human-readable logs. Test and production environments emit
one JSON object per log record.

Common JSON log fields:

| Field | Description |
| --- | --- |
| `timestamp` | UTC ISO-8601 timestamp. |
| `level` | Python log level. |
| `logger` | Logger name, for example `api.request` or `api.error`. |
| `message` | Stable event message. |
| `request_id` | `X-Request-ID` value or generated UUID. |
| `trace_id` | Current OpenTelemetry trace ID when tracing is enabled. |
| `service` | Object with `name`, `version`, and `environment`. |

Access logs from `api.request` also include:

| Field | Description |
| --- | --- |
| `method` | HTTP method. |
| `path` | Request path. |
| `status_code` | Response status code. |
| `duration_ms` | Request duration in milliseconds. |

Unhandled exceptions are logged through `api.error` with `method`, `path`,
`status_code`, `error_type`, and exception traceback metadata.

Clients can pass `X-Request-ID` with up to 64 alphanumeric, dash, or underscore
characters. Invalid or missing values are replaced with a generated UUID.

## Error reporting

Unhandled exceptions route through a pluggable `ErrorReporterPort` seam
(`src/app_platform/observability/error_reporter.py`). The default
`LoggingErrorReporter` emits a structured WARN log; the optional
`SentryErrorReporter` forwards to Sentry when the `sentry` extra is
installed and `APP_SENTRY_DSN` is set.

### Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `APP_SENTRY_DSN` | unset | Activates `SentryErrorReporter` when the `sentry` extra is installed. Otherwise `LoggingErrorReporter` is used. |
| `APP_SENTRY_ENVIRONMENT` | unset | Forwarded to `sentry_sdk.init(environment=...)`. |
| `APP_SENTRY_RELEASE` | unset | Forwarded to `sentry_sdk.init(release=...)`. |

The Sentry SDK's `traces_sample_rate` is bound to
`APP_OTEL_TRACES_SAMPLER_RATIO` so OTel and Sentry sampling stay in sync.

Install the optional extra to opt into Sentry:

```bash
pip install '.[sentry]'
# or
uv sync --extra sentry
```

### Reporter selection rule

The factory picks the reporter deterministically at startup and emits one
of these log lines:

1. `APP_SENTRY_DSN` set **and** `sentry_sdk` importable →
   `SentryErrorReporter` is wired; `sentry_sdk.init(...)` is called with
   `dsn`, `environment`, `release`, and `traces_sample_rate`.
2. `APP_SENTRY_DSN` set **and** `sentry_sdk` NOT importable →
   `LoggingErrorReporter` is wired plus a WARN log line naming the
   missing extra (`pip install '.[sentry]'`).
3. `APP_SENTRY_DSN` unset → `LoggingErrorReporter` is wired plus an INFO
   log line announcing the chosen reporter.

`APP_SENTRY_DSN` is NOT a production refusal: paging is an operator
choice, not a safety invariant. Operators on internal-only deployments
may legitimately not have paging.

### Context attached to every capture

`unhandled_exception_handler` calls the reporter with these context keys:

| Key | Source |
| --- | --- |
| `request_id` | `RequestContextMiddleware` (`X-Request-ID` or generated UUID4). |
| `path` | `request.url.path`. |
| `method` | HTTP method. |
| `principal_id` | `request.state.principal_id` when the principal resolver set it; otherwise `None`. |

The `SentryErrorReporter` adapter writes these to a single Sentry context
namespace (`request`). The `LoggingErrorReporter` writes them as
structured `extra` fields on the log record.

### Mapped 4xx responses are NOT reported

Only exceptions that fall through every other registered handler (i.e.
unhandled exceptions producing a 500) route through the reporter. Mapped
4xx responses (`ApplicationHTTPException`, `RequestValidationError`,
generic `StarletteHTTPException`, the dependency-container readiness
error) skip the reporter — they are not pages.

### Swapping the reporter in tests

The reporter is bound on `app.state.error_reporter` after
`build_fastapi_app` returns. Tests can substitute a fake recorder
without monkeypatching `sentry_sdk`:

```python
class FakeReporter:
    def __init__(self) -> None:
        self.calls: list[tuple[BaseException, dict[str, object]]] = []

    def capture(self, exc: BaseException, **context: object) -> None:
        self.calls.append((exc, context))


app = build_fastapi_app(settings)
app.state.error_reporter = FakeReporter()
```

The contract is documented on `ErrorReporterPort` in
`src/app_platform/observability/error_reporter.py`; any object with a
`capture(exc, **context)` method that does not raise is a valid reporter.
