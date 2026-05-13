"""Unit tests for :class:`SecurityHeadersMiddleware`."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app_platform.api.app_factory import build_fastapi_app
from app_platform.config.settings import AppSettings

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
    assert resp.headers["content-security-policy"] == "default-src 'none'"
    assert resp.headers["cross-origin-opener-policy"] == "same-origin"
    assert resp.headers["cross-origin-resource-policy"] == "same-origin"
    perm_policy = resp.headers["permissions-policy"]
    # A handful of representative features should be locked down explicitly.
    for disabled in ("camera=()", "microphone=()", "geolocation=()", "payment=()"):
        assert disabled in perm_policy


def test_hsts_absent_outside_production(test_settings: AppSettings) -> None:
    with TestClient(_app(test_settings)) as c:
        resp = c.get("/__ping")
    assert "strict-transport-security" not in resp.headers


def test_hsts_includes_preload_in_production(test_settings: AppSettings) -> None:
    settings = test_settings.model_copy(update={"environment": "production"})
    with TestClient(_app(settings)) as c:
        resp = c.get("/__ping")
    assert resp.headers["strict-transport-security"] == (
        "max-age=31536000; includeSubDomains; preload"
    )
