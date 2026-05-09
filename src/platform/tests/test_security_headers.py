"""Unit tests for :class:`SecurityHeadersMiddleware`."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.platform.api.app_factory import build_fastapi_app
from src.platform.config.settings import AppSettings

pytestmark = pytest.mark.unit


def _app(settings: AppSettings) -> FastAPI:
    app = build_fastapi_app(settings)

    @app.get("/__ping")
    def _ping() -> dict[str, str]:
        return {"ok": "pong"}

    return app


def test_security_headers_present(test_settings: AppSettings) -> None:
    with TestClient(_app(test_settings)) as c:
        resp = c.get("/__ping")
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.headers["x-frame-options"] == "DENY"
    assert resp.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert resp.headers["x-xss-protection"] == "0"


def test_hsts_absent_outside_production(test_settings: AppSettings) -> None:
    with TestClient(_app(test_settings)) as c:
        resp = c.get("/__ping")
    assert "strict-transport-security" not in resp.headers
