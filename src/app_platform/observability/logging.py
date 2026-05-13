"""Structured logging configuration with request-id and trace-id correlation.

The ``RequestContextMiddleware`` populates :data:`REQUEST_ID_CONTEXT` per
request; :class:`RequestIdFilter` reads that contextvar and stamps it onto
every log record so business-logic logs share the same request id as the
access log without callers having to thread it through manually.

When OpenTelemetry is active, :class:`RequestIdFilter` reads the current span
and stamps its trace ID onto every log record. :data:`TRACE_ID_CONTEXT` remains
available as an explicit fallback for code that needs to set trace context
outside an active span.

In non-development environments the root logger is configured with
:class:`JsonFormatter`, which emits one JSON object per record so log
aggregators (CloudWatch, GCP Logging, Loki, Datadog) can parse fields
directly. In development the standard human-readable formatter is kept.
"""

from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

REQUEST_ID_CONTEXT: ContextVar[str | None] = ContextVar("request_id", default=None)
TRACE_ID_CONTEXT: ContextVar[str | None] = ContextVar("trace_id", default=None)

# Standard LogRecord attributes — anything not in this set is treated as
# user-supplied ``extra`` context and surfaced in the JSON payload.
_STANDARD_LOGRECORD_ATTRS = frozenset(
    {
        "args",
        "asctime",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "message",
        "module",
        "msecs",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "thread",
        "threadName",
        "taskName",
        "request_id",
        "trace_id",
    }
)


class RequestIdFilter(logging.Filter):
    """Inject :data:`REQUEST_ID_CONTEXT` and :data:`TRACE_ID_CONTEXT` onto records."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = REQUEST_ID_CONTEXT.get()
        record.trace_id = _get_otel_trace_id() or TRACE_ID_CONTEXT.get()
        return True


def _get_otel_trace_id() -> str | None:
    """Return the current OTel trace ID as a hex string, or None if not tracing."""
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        ctx = span.get_span_context()
        if ctx.is_valid:
            return format(ctx.trace_id, "032x")
    except Exception:  # noqa: S110 — log-formatter best-effort; never block emission
        pass
    return None


class JsonFormatter(logging.Formatter):
    """Emit one JSON object per log record with stable top-level keys.

    Top-level keys:
    - ``timestamp``: ISO-8601 UTC
    - ``level``: log level name
    - ``logger``: logger name
    - ``message``: formatted message
    - ``request_id``: from :data:`REQUEST_ID_CONTEXT` (null if outside a request)
    - ``trace_id``: OTel trace id (null if tracing is disabled)
    - ``service``: dict with ``name``, ``version``, ``environment``
    - Any ``extra`` fields passed by the caller
    """

    def __init__(
        self,
        *,
        service_name: str = "starter-template-fastapi",
        service_version: str = "unknown",
        environment: str = "development",
    ) -> None:
        super().__init__()
        self._service = {
            "name": service_name,
            "version": service_version,
            "environment": environment,
        }

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", None),
            "trace_id": getattr(record, "trace_id", None),
            "service": self._service,
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        # Forward any ``extra={...}`` fields the caller passed.
        for key, value in record.__dict__.items():
            if key in _STANDARD_LOGRECORD_ATTRS or key.startswith("_"):
                continue
            payload[key] = value
        return json.dumps(payload, default=str)


def configure_logging(
    *,
    level: str,
    json_format: bool,
    service_name: str = "starter-template-fastapi",
    service_version: str = "unknown",
    environment: str = "development",
) -> None:
    """Configure the root logger with a single stdout handler.

    Idempotent: replaces any previously-installed handlers so calling this
    twice in a process (tests, ``create_app`` reuse) does not duplicate
    output.

    Args:
        level: Root log level (e.g. ``"INFO"``).
        json_format: If ``True``, use :class:`JsonFormatter`; otherwise use
            human-readable format for local development.
        service_name: Embedded in every JSON record as ``service.name``.
        service_version: Embedded as ``service.version``.
        environment: Embedded as ``service.environment``.
    """
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    handler = logging.StreamHandler(stream=sys.stdout)
    handler.addFilter(RequestIdFilter())
    if json_format:
        handler.setFormatter(
            JsonFormatter(
                service_name=service_name,
                service_version=service_version,
                environment=environment,
            )
        )
    else:
        handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%S%z",
            )
        )

    root = logging.getLogger()
    for existing in list(root.handlers):
        root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(numeric_level)
    # Align uvicorn's loggers with the root configuration so access logs
    # and error logs share the same format and request-id correlation.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uv_logger = logging.getLogger(name)
        uv_logger.handlers.clear()
        uv_logger.propagate = True
