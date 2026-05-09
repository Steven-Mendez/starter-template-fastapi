"""Unit tests for platform observability."""

from __future__ import annotations

import json
import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.platform.api.app_factory import build_fastapi_app
from src.platform.config.settings import AppSettings
from src.platform.observability.logging import (
    REQUEST_ID_CONTEXT,
    TRACE_ID_CONTEXT,
    JsonFormatter,
    RequestIdFilter,
)
from src.platform.observability.tracing import instrument_fastapi_app

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# /metrics endpoint
# ---------------------------------------------------------------------------


def _app(*, metrics_enabled: bool = True) -> FastAPI:
    settings = AppSettings(
        environment="test",
        auth_jwt_secret_key="test-secret-key-with-at-least-32-bytes",
        auth_redis_url=None,
        metrics_enabled=metrics_enabled,
    )
    return build_fastapi_app(settings)


def test_metrics_endpoint_is_available_by_default() -> None:
    client = TestClient(_app(metrics_enabled=True))
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "python_info" in resp.text or "http_requests" in resp.text


def test_metrics_endpoint_absent_when_disabled() -> None:
    client = TestClient(_app(metrics_enabled=False))
    resp = client.get("/metrics")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# JsonFormatter - service context and extra fields
# ---------------------------------------------------------------------------


def _record(message: str, **extra: object) -> logging.LogRecord:
    record = logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname=__file__,
        lineno=0,
        msg=message,
        args=(),
        exc_info=None,
    )
    record.request_id = None
    record.trace_id = None
    for k, v in extra.items():
        setattr(record, k, v)
    return record


def test_json_formatter_includes_service_context() -> None:
    fmt = JsonFormatter(
        service_name="my-service",
        service_version="1.2.3",
        environment="production",
    )
    payload = json.loads(fmt.format(_record("hello")))
    assert payload["service"] == {
        "name": "my-service",
        "version": "1.2.3",
        "environment": "production",
    }


def test_json_formatter_includes_extra_fields() -> None:
    fmt = JsonFormatter()
    record = _record("event")
    record.method = "POST"  # type: ignore[attr-defined]
    record.path = "/auth/login"  # type: ignore[attr-defined]
    payload = json.loads(fmt.format(record))
    assert payload["method"] == "POST"
    assert payload["path"] == "/auth/login"


def test_json_formatter_includes_request_id_from_contextvar() -> None:
    fmt = JsonFormatter()
    flt = RequestIdFilter()

    token = REQUEST_ID_CONTEXT.set("req-abc-123")
    try:
        record = _record("with-context")
        flt.filter(record)
        payload = json.loads(fmt.format(record))
        assert payload["request_id"] == "req-abc-123"
    finally:
        REQUEST_ID_CONTEXT.reset(token)


def test_json_formatter_null_request_id_outside_request() -> None:
    fmt = JsonFormatter()
    flt = RequestIdFilter()
    record = _record("no context")
    flt.filter(record)
    payload = json.loads(fmt.format(record))
    assert payload["request_id"] is None


def test_json_formatter_includes_trace_id_from_contextvar() -> None:
    fmt = JsonFormatter()
    flt = RequestIdFilter()

    token = TRACE_ID_CONTEXT.set("trace-abc-123")
    try:
        record = _record("with-trace-context")
        flt.filter(record)
        payload = json.loads(fmt.format(record))
        assert payload["trace_id"] == "trace-abc-123"
    finally:
        TRACE_ID_CONTEXT.reset(token)


def test_fastapi_tracing_noops_when_endpoint_unset() -> None:
    settings = AppSettings(
        environment="test",
        auth_jwt_secret_key="test-secret-key-with-at-least-32-bytes",
        otel_exporter_endpoint=None,
    )
    app = FastAPI()

    instrument_fastapi_app(app, settings)

    assert not getattr(app.state, "otel_instrumented", False)


def test_error_log_uses_extra_not_raw_json(caplog: pytest.LogCaptureFixture) -> None:
    """Error handlers should log structured extra, not raw JSON."""
    settings = AppSettings(
        environment="test",
        auth_jwt_secret_key="test-secret-key-with-at-least-32-bytes",
        auth_redis_url=None,
    )
    app = build_fastapi_app(settings)

    @app.get("/__boom")
    def boom() -> None:
        raise RuntimeError("test error")

    with caplog.at_level(logging.ERROR, logger="api.error"):
        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.get("/__boom")

    assert resp.status_code == 500
    assert any(
        "test error" in r.getMessage() or "Unhandled" in r.getMessage()
        for r in caplog.records
    )
    # The message must NOT be a raw JSON string; it should be the log message,
    # with error details in ``extra`` attributes on the LogRecord.
    for record in caplog.records:
        msg = record.getMessage()
        # A raw-JSON log would start with '{' — verify it doesn't.
        assert not msg.strip().startswith("{"), (
            f"error_handlers emitted raw JSON instead of structured extra: {msg!r}"
        )
