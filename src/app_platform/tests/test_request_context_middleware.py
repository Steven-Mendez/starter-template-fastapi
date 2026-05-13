"""Test support for request context middleware."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app_platform.api.app_factory import build_fastapi_app
from app_platform.config.settings import AppSettings

pytestmark = pytest.mark.unit


def _ping_app(settings: AppSettings) -> FastAPI:
    app = build_fastapi_app(settings)

    @app.get("/__ping")
    def _ping() -> dict[str, str]:
        return {"ok": "pong"}

    return app


def test_request_id_is_generated(test_settings: AppSettings) -> None:
    with TestClient(_ping_app(test_settings)) as c:
        resp = c.get("/__ping")
    assert resp.headers["X-Request-ID"]
    assert len(resp.headers["X-Request-ID"]) >= 8


def test_request_id_echoed(test_settings: AppSettings) -> None:
    with TestClient(_ping_app(test_settings)) as c:
        resp = c.get("/__ping", headers={"X-Request-ID": "abc-123"})
    assert resp.headers["X-Request-ID"] == "abc-123"


def test_invalid_request_id_is_replaced(test_settings: AppSettings) -> None:
    with TestClient(_ping_app(test_settings)) as c:
        resp = c.get("/__ping", headers={"X-Request-ID": "<script>alert(1)</script>"})
    returned_id = resp.headers["X-Request-ID"]
    assert "<script>" not in returned_id
    import uuid

    uuid.UUID(returned_id)


def test_too_long_request_id_is_replaced(test_settings: AppSettings) -> None:
    long_id = "a" * 65
    with TestClient(_ping_app(test_settings)) as c:
        resp = c.get("/__ping", headers={"X-Request-ID": long_id})
    assert resp.headers["X-Request-ID"] != long_id


def test_access_log_emitted(
    test_settings: AppSettings, caplog: pytest.LogCaptureFixture
) -> None:
    import logging

    caplog.set_level(logging.INFO, logger="api.request")
    with TestClient(_ping_app(test_settings)) as c:
        c.get("/__ping")
    records = [r for r in caplog.records if r.name == "api.request"]
    assert any(getattr(r, "path", None) == "/__ping" for r in records)
    assert any(getattr(r, "status_code", None) == 200 for r in records)
    assert all(not r.getMessage().strip().startswith("{") for r in records)
