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
- SQLAlchemy/SQLModel database calls.
- Redis calls when `APP_AUTH_REDIS_URL` is set.

Health and metrics routes are excluded from FastAPI spans.

When `APP_OTEL_EXPORTER_ENDPOINT` is unset, tracing instrumentation is not
installed and OpenTelemetry stays on its default no-op provider.

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
