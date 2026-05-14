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
| `APP_HEALTH_READY_PROBE_TIMEOUT_SECONDS` | `1.0` | Per-dependency timeout for `GET /health/ready`. Must be in `(0.0, 30.0]`. |

## Health probes

The service exposes two health endpoints with different semantics. Configure
the kubelet to point liveness at `/health/live` and readiness at
`/health/ready`; do not collapse them onto a single URL.

| Endpoint | Purpose | Touches dependencies? | Use for |
| --- | --- | --- | --- |
| `GET /health/live` | "Is the process able to serve any request?" | No — process-only, returns 200 unconditionally. | `livenessProbe`. The kubelet restarts the pod when this fails. |
| `GET /health/ready` | "Should the load balancer send this pod traffic?" | Yes — pings every configured dependency. | `readinessProbe`. The kubelet drops the pod from the Service when this fails. |

`/health/ready` runs in parallel:

- `SELECT 1` against PostgreSQL.
- `PING` against Redis when `APP_AUTH_REDIS_URL` (or `APP_JOBS_REDIS_URL`) is configured.
- `head_bucket` against S3 when `APP_STORAGE_ENABLED=true` and `APP_STORAGE_BACKEND=s3`.

Each probe is bounded by `APP_HEALTH_READY_PROBE_TIMEOUT_SECONDS` (default
`1.0`). Probes run via `asyncio.gather`, so the worst-case probe latency is
the slowest single dependency — not the sum.

Response shapes:

| Condition | Status | Body | Headers |
| --- | --- | --- | --- |
| Lifespan startup not yet complete (registries unsealed, containers unwired). | `503` | `{"status":"starting"}` | none |
| Every configured dependency responds within its timeout. | `200` | `{"status":"ok","deps":{...}}` | none |
| Any configured dependency times out or raises. | `503` | `{"status":"fail","deps":{"<name>":{"status":"fail","reason":"..."}, ...}}` | `Retry-After: 1` |

The readiness flag flips at the END of FastAPI lifespan startup (after every
feature registry is sealed and every container is attached) and is cleared at
the START of shutdown, so `SIGTERM` immediately drops the pod from rotation
even before in-flight requests drain. This is the contract `add-graceful-shutdown`
depends on.

Both `/health/live` and `/health/ready` are excluded from Prometheus HTTP
metrics and OTel spans so kubelet polling does not flood your dashboards.

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

### Producer pipeline

The platform owns a single `opentelemetry.sdk.metrics.MeterProvider`
wired to a `PrometheusMetricReader` from `opentelemetry-exporter-prometheus`.
The reader registers itself against `prometheus_client.REGISTRY` and the
`/metrics` route is an ASGI mount of `prometheus_client.make_asgi_app()`,
so the same SDK / exporter pipeline serves both metrics and traces.

Features MUST obtain a `Meter` through the platform factory:

```python
from app_platform.observability.metrics import get_app_meter

meter = get_app_meter("my_feature")  # instrumentation-scope name
counter = meter.create_counter(
    name="app_myfeature_widgets_total",
    description="Total widgets processed, labelled by outcome.",
    unit="1",
)
```

`get_app_meter(feature)` is the single contract: it builds the
`MeterProvider` on first call and caches it module-level. Features MUST
NOT call `opentelemetry.metrics.get_meter(...)` directly — going through
the factory keeps naming, sampling defaults, and test isolation in one
place.

### Naming convention

`app_<feature>_<noun>_<unit>`:

| Element | Rule |
| --- | --- |
| `app_` prefix | Avoids collision with auto-instrumentation (HTTP request, DB query, etc.). |
| `_total` suffix | Monotonic counters. |
| `_gauge` suffix | Observable gauges. |
| `_seconds` suffix | Durations (reserved for future histograms). |
| Labels | Closed set, bounded cardinality. No user-id, no path-templated cardinality. |

### Catalog

| Metric | Type | Labels | Source |
| --- | --- | --- | --- |
| `app_auth_logins_total` | Counter | `result ∈ {success, failure}` | `LoginUser.execute` — exactly one increment per call. |
| `app_auth_refresh_total` | Counter | `result ∈ {success, failure}` | `RotateRefreshToken.execute` — exactly one increment per call. |
| `app_outbox_dispatched_total` | Counter | `result ∈ {success, failure}` | `DispatchPending.execute` — one increment per row, AFTER the per-row commit. Rows that schedule a retry are not counted (still pending). |
| `app_jobs_enqueued_total` | Counter | `handler` (bounded by `JobHandlerRegistry`) | `InProcessJobQueueAdapter.enqueue` and `ArqJobQueueAdapter.enqueue`. |
| `app_outbox_pending_gauge` | Observable gauge | — | Bound at composition in `main.py`; runs `SELECT COUNT(*) FROM outbox_messages WHERE status='pending'` against the engine with `SET LOCAL statement_timeout='2s'` (PostgreSQL) so a slow DB cannot stall the scrape. Query failures are logged and the gauge drops out of the scrape (no 500). |
| `app_db_pool_checked_in` | Observable gauge | — | `engine.pool.checkedin()` — connections currently idle. |
| `app_db_pool_checked_out` | Observable gauge | — | `engine.pool.checkedout()` — connections currently in use. |
| `app_db_pool_overflow` | Observable gauge | — | `engine.pool.overflow()` — connections above the configured pool size. |
| `app_db_pool_size` | Observable gauge | — | `engine.pool.size()` — configured pool size. |

New metrics are added by declaring instruments against
`get_app_meter("<feature>")` in `app_platform.observability.metrics` (or
in the feature's own composition module if the metric is feature-local)
and wiring exactly one production call site per increment.

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

### Trace propagation across the queue boundary

A request that enqueues background work (e.g. a password-reset that
queues `send_email` through the outbox) propagates the W3C
`traceparent`/`tracestate` carrier so the handler's spans become
children of the originating request's trace. The full causal chain is:

```
HTTP request span
   └─ outbox.enqueue (column captures traceparent)
        └─ outbox.dispatch_pending  (relay tick)
             └─ outbox.dispatch_row (injects payload["__trace"])
                  └─ jobs.in_process|arq.handler (extracts + attaches)
                       └─ handler-side spans (email send, file write, …)
```

Mechanism:

1. `SessionSQLModelOutboxAdapter.enqueue` calls
   `propagator_inject_current()` to capture the active context as a
   W3C carrier dict and persists it into the
   `outbox_messages.trace_context` JSONB column inside the producer
   transaction.
2. `DispatchPending` copies the column into the dispatched payload
   under the reserved key `__trace` (alongside `__outbox_message_id`).
   See `docs/outbox.md` for the reserved-key table.
3. The job entrypoint (in-process adapter or the arq handler wrapper)
   extracts the carrier and calls `context.attach(ctx)` before
   invoking the handler, then `context.detach(token)` in a `finally`
   block so the active context is restored even on handler errors.

Direct (non-outbox) `JobQueuePort.enqueue` call sites — the GDPR
`erase_user` HTTP routes today — inject `__trace` inline via the same
`propagator_inject_current()` helper.

Legacy outbox rows that predate the `trace_context` column carry an
empty carrier (`'{}'::jsonb`); the relay tolerates this and the
handler simply starts a fresh trace.

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

Access logs are emitted by `AccessLogMiddleware` (`api.access`), mounted inner
to `RequestContextMiddleware`. Uvicorn's built-in access log is suppressed
(its record runs outside the request-id contextvar window and would otherwise
emit `request_id=null` for every line).

### PII / token redaction

Two seams cooperate to keep PII and single-use tokens out of logs:

1. **Structlog processor** —
   `app_platform.observability.pii_filter.PiiRedactionProcessor` walks an
   event dict by key (case-insensitive) and applies the policy below.
   Installed in the structlog processor chain if/when structlog is wired in.
2. **Stdlib filter** —
   `app_platform.observability.pii_filter.PiiLogFilter` is mounted on every
   root log handler so the same policy applies to plain-stdlib log records
   (uvicorn, third-party libraries). It walks `record.args` (when mapping-
   shaped) and any `extra={...}` attributes promoted onto the record.

The redaction policy is a closed key-name allowlist defined in
`app_platform.observability.redaction`:

| Constant | Keys | Treatment |
| --- | --- | --- |
| `REDACT_STRICT_KEYS` | `password`, `password_hash`, `hash`, `token`, `access_token`, `refresh_token`, `authorization`, `cookie`, `set-cookie`, `secret`, `api_key`, `phone` | Value replaced with `"***REDACTED***"`. |
| `REDACT_EMAIL_KEYS` | `email`, `to`, `from`, `recipient`, `cc`, `bcc` | String values passed through `redact_email` (e.g. `a***@example.com`). Non-string values left untouched. |
| `REDACT_HEADER_NAMES` | `authorization`, `cookie`, `set-cookie`, `proxy-authorization`, `x-api-key`, `x-auth-token` | When an event carries a `headers` / `request.headers` / `response.headers` mapping, header names in this set are replaced with `"***REDACTED***"`. The strict/email rules also apply within the headers mapping. |

Matching is case-insensitive on the exact key name. **Value scanning / regex
sweeps over message strings are explicitly out of scope** — the filter is a
safety net, not regulatory-grade DLP. Call-site redaction
(`to=redact_email(to)`) is the recommended approach for string-formatted log
calls. `redact_email` is the public helper for that.

`docs/email.md` documents the related rule for the console adapter: the
rendered body is never logged by default. Operators correlate by
`body_sha256` instead. To opt into full-body logging during local development,
set both `APP_EMAIL_CONSOLE_LOG_BODIES=true` and `APP_ENVIRONMENT=development`.

| Variable | Default | Purpose |
| --- | --- | --- |
| `APP_EMAIL_CONSOLE_LOG_BODIES` | `false` | When `true` AND `APP_ENVIRONMENT=development`, the console email adapter additionally logs the rendered body. The redacted `body_len`/`body_sha256` line is always emitted regardless. |

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
