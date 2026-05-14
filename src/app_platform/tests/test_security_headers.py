"""Unit tests for :class:`SecurityHeadersMiddleware`.

The middleware enforces the strict baseline described in
``openspec/changes/harden-http-middleware-stack/design.md``:

- ``Content-Security-Policy: default-src 'none'; frame-ancestors 'none'``
  on every JSON response.
- ``Referrer-Policy: no-referrer``.
- ``X-Content-Type-Options: nosniff``.
- ``Permissions-Policy: ()``.
- ``Strict-Transport-Security`` only in production.
- ``Server`` / ``X-Powered-By`` stripped on the way out.

A relaxed CSP is applied on the FastAPI docs surface
(``/docs``, ``/docs/oauth2-redirect``, ``/redoc``, ``/openapi.json``)
when ``APP_ENABLE_DOCS=true``.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI, Response
from fastapi.testclient import TestClient

from app_platform.api.app_factory import build_fastapi_app
from app_platform.config.settings import AppSettings

pytestmark = pytest.mark.unit


_STRICT_CSP = "default-src 'none'; frame-ancestors 'none'"


def _app(settings: AppSettings) -> FastAPI:
    app = build_fastapi_app(settings)

    @app.get("/__ping")
    def _ping() -> dict[str, str]:
        return {"ok": "pong"}

    return app


def test_strict_baseline_headers_present_on_json_endpoint(
    test_settings: AppSettings,
) -> None:
    """Every JSON endpoint carries the strict baseline security headers."""
    with TestClient(_app(test_settings)) as c:
        resp = c.get("/__ping")
    assert resp.status_code == 200
    # Strict CSP — JSON endpoints never need to load any subresource.
    assert resp.headers["content-security-policy"] == _STRICT_CSP
    assert resp.headers["referrer-policy"] == "no-referrer"
    assert resp.headers["x-content-type-options"] == "nosniff"
    # Permissions-Policy: empty policy denies every browser feature.
    assert resp.headers["permissions-policy"] == "()"


def test_stack_identity_headers_stripped_when_inner_route_sets_them(
    test_settings: AppSettings,
) -> None:
    """``Server`` / ``X-Powered-By`` set by an inner route are stripped on the way out.

    ``TestClient`` does not inject either header on its own, so a test
    that simply asserts they are absent on a vanilla endpoint passes
    vacuously. Instead we deliberately set both headers from a route
    handler and verify the middleware strips them before the response
    leaves the stack.

    In production the same strip code runs as defense-in-depth for any
    upstream layer (a reverse proxy, a future feature) that might add
    them; uvicorn's ``Server: uvicorn`` header itself is added at the
    HTTP layer **after** the ASGI chain runs and is suppressed via the
    ``--no-server-header`` CLI flag baked into the Dockerfile (see
    ``docs/operations.md``).
    """
    app = build_fastapi_app(test_settings)

    @app.get("/__leaky")
    def _leaky() -> Response:
        return Response(
            content=b'{"ok":true}',
            media_type="application/json",
            headers={
                "Server": "leaky-stack/9.9",
                "X-Powered-By": "Express",
            },
        )

    with TestClient(app) as c:
        resp = c.get("/__leaky")
    assert resp.status_code == 200
    # The middleware-level strip code must remove both headers.
    lowercased = {k.lower() for k in resp.headers}
    assert "server" not in lowercased
    assert "x-powered-by" not in lowercased


def test_hsts_absent_outside_production(test_settings: AppSettings) -> None:
    """HSTS is only meaningful behind TLS; never emitted outside production."""
    with TestClient(_app(test_settings)) as c:
        resp = c.get("/__ping")
    assert "strict-transport-security" not in resp.headers


def test_hsts_includes_preload_in_production(test_settings: AppSettings) -> None:
    """In production HSTS pins a one-year window with subdomains + preload."""
    settings = test_settings.model_copy(update={"environment": "production"})
    with TestClient(_app(settings)) as c:
        resp = c.get("/__ping")
    assert resp.headers["strict-transport-security"] == (
        "max-age=31536000; includeSubDomains; preload"
    )


def test_strict_csp_applied_when_docs_disabled(test_settings: AppSettings) -> None:
    """With docs off, the strict CSP is the only one observed on JSON paths."""
    settings = test_settings.model_copy(update={"enable_docs": False})
    with TestClient(_app(settings)) as c:
        resp = c.get("/__ping")
    assert resp.status_code == 200
    assert resp.headers["content-security-policy"] == _STRICT_CSP


def test_docs_route_not_mounted_when_docs_disabled(
    test_settings: AppSettings,
) -> None:
    """``/docs`` is not mounted when ``APP_ENABLE_DOCS=false``."""
    settings = test_settings.model_copy(update={"enable_docs": False})
    with TestClient(_app(settings)) as c:
        resp = c.get("/docs")
    # FastAPI returns 404 for unmounted docs URLs.
    assert resp.status_code == 404
    # Even the 404 carries the strict CSP since the middleware fires regardless.
    assert resp.headers["content-security-policy"] == _STRICT_CSP


def test_docs_route_carries_relaxed_csp_when_docs_enabled(
    test_settings: AppSettings,
) -> None:
    """``/docs`` carries the relaxed CSP allowing jsdelivr-hosted assets."""
    # test_settings already has enable_docs=True.
    with TestClient(_app(test_settings)) as c:
        resp = c.get("/docs")
    assert resp.status_code == 200
    csp = resp.headers["content-security-policy"]
    # Swagger needs jsdelivr for script and style, plus inline scripts.
    assert "https://cdn.jsdelivr.net" in csp
    assert "'unsafe-inline'" in csp
    assert "frame-ancestors 'none'" in csp
    # Crucially, the strict policy is NOT applied here.
    assert csp != _STRICT_CSP


def test_openapi_json_carries_relaxed_csp_when_docs_enabled(
    test_settings: AppSettings,
) -> None:
    """``/openapi.json`` is part of the docs surface and gets the relaxed CSP."""
    with TestClient(_app(test_settings)) as c:
        resp = c.get("/openapi.json")
    assert resp.status_code == 200
    csp = resp.headers["content-security-policy"]
    assert "https://cdn.jsdelivr.net" in csp
    assert csp != _STRICT_CSP


def test_redoc_route_carries_relaxed_csp_when_docs_enabled(
    test_settings: AppSettings,
) -> None:
    """``/redoc`` is part of the docs surface and gets the relaxed CSP."""
    with TestClient(_app(test_settings)) as c:
        resp = c.get("/redoc")
    assert resp.status_code == 200
    csp = resp.headers["content-security-policy"]
    assert "https://cdn.jsdelivr.net" in csp
    assert csp != _STRICT_CSP


def test_non_docs_route_keeps_strict_csp_when_docs_enabled(
    test_settings: AppSettings,
) -> None:
    """The relaxed CSP only applies to docs paths, not every endpoint."""
    with TestClient(_app(test_settings)) as c:
        resp = c.get("/__ping")
    assert resp.status_code == 200
    # Even with docs enabled, non-docs paths get the strict policy.
    assert resp.headers["content-security-policy"] == _STRICT_CSP
