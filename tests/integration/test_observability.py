from __future__ import annotations

import json
import logging

import pytest
from _pytest.logging import LogCaptureFixture
from fastapi.testclient import TestClient

from main import create_app
from src.config.settings import AppSettings

pytestmark = pytest.mark.integration


def test_health_reports_persistence_readiness(api_client: TestClient) -> None:
    response = api_client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["persistence"]["backend"] == "postgresql"
    assert payload["persistence"]["ready"] is True


def test_request_logging_emits_structured_fields(
    api_client: TestClient, caplog: LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="api.request")
    response = api_client.get("/health", headers={"X-Request-ID": "log-req-1"})
    assert response.status_code == 200
    records = [r for r in caplog.records if r.name == "api.request"]
    assert records
    payload = json.loads(records[-1].message)
    assert payload["request_id"] == "log-req-1"
    assert payload["method"] == "GET"
    assert payload["path"] == "/health"
    assert payload["status_code"] == 200
    assert isinstance(payload["duration_ms"], float)


def test_unhandled_exception_logging_emits_structured_fields(
    postgresql_dsn: str,
    caplog: LogCaptureFixture,
) -> None:
    app = create_app(
        AppSettings(
            postgresql_dsn=postgresql_dsn,
        )
    )

    @app.get("/explode")
    def explode() -> dict[str, str]:
        raise RuntimeError("boom")

    caplog.set_level(logging.ERROR, logger="api.error")
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/explode", headers={"X-Request-ID": "err-req-1"})

    assert response.status_code == 500
    records = [r for r in caplog.records if r.name == "api.error"]
    assert records
    payload = json.loads(records[-1].message)
    assert payload["request_id"] == "err-req-1"
    assert payload["method"] == "GET"
    assert payload["path"] == "/explode"
    assert payload["status_code"] == 500
    assert payload["error_type"] == "RuntimeError"
