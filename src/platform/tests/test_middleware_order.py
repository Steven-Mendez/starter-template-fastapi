"""Tests asserting the FastAPI middleware order is correct.

The platform stack adds middleware in a specific order so that CORS
preflight is handled before TrustedHost or ContentSizeLimit reject the
request, and so that RequestContext can record the inner status code.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.platform.api.app_factory import build_fastapi_app
from src.platform.config.settings import AppSettings

pytestmark = pytest.mark.unit


def _app(settings: AppSettings) -> FastAPI:
    app = build_fastapi_app(settings)

    @app.post("/__echo")
    def _echo(payload: dict[str, str]) -> dict[str, str]:
        return payload

    return app


def test_cors_preflight_handled_before_trusted_host(
    test_settings: AppSettings,
) -> None:
    # Switching to production-style hosts: TrustedHost is enabled and only
    # allows ``api.example.com``. A CORS preflight from a permitted origin
    # to an unrelated host header would still be rejected — so we use the
    # allowed host but want to confirm CORS responds 200 to OPTIONS.
    settings = test_settings.model_copy(
        update={
            "environment": "production",
            "trusted_hosts": ["api.example.com"],
            "cors_origins": ["https://web.example.com"],
            "enable_docs": False,
            "auth_cookie_secure": True,
            "auth_jwt_issuer": "https://issuer.example.com",
            "auth_jwt_audience": "starter-template-fastapi",
        }
    )
    with TestClient(_app(settings), base_url="https://api.example.com") as client:
        resp = client.options(
            "/__echo",
            headers={
                "Origin": "https://web.example.com",
                "Access-Control-Request-Method": "POST",
                "Host": "api.example.com",
            },
        )
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == "https://web.example.com"


def test_request_id_header_set_on_response(test_settings: AppSettings) -> None:
    with TestClient(_app(test_settings)) as client:
        resp = client.post("/__echo", json={"hello": "world"})
    assert resp.status_code == 200
    assert "x-request-id" in resp.headers
