from __future__ import annotations

import json
import logging

import pytest
from _pytest.logging import LogCaptureFixture
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


def test_health_reports_persistence_readiness(api_client: TestClient) -> None:
    response = api_client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["persistence"]["backend"] in {"inmemory", "sqlite"}
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
