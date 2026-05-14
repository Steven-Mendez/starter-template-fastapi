"""Trusted-proxy IP resolution for the auth layer.

Covers task 5.1 from ``harden-rate-limiting``: the ``_client_ip`` helper
in ``adapters/inbound/http/auth.py`` returns the rewritten client IP
when the request originated from a trusted proxy (via
``X-Forwarded-For``), and the unmodified socket peer when the proxy is
NOT trusted.

The behaviour is implemented by ``uvicorn.middleware.proxy_headers
.ProxyHeadersMiddleware`` (installed in
``app_platform.api.app_factory.build_fastapi_app`` when
``APP_TRUSTED_PROXY_IPS`` is non-empty). We test the helper through a
minimal FastAPI app rather than mocking the middleware so we exercise
the real rewrite path the production composition uses.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from features.authentication.adapters.inbound.http.auth import _client_ip

pytestmark = pytest.mark.unit


def _build_app(trusted_hosts: list[str] | str) -> FastAPI:
    """Build a FastAPI app whose ``/peek`` route returns ``_client_ip(request)``."""
    app = FastAPI()

    @app.get("/peek")
    def peek(request: Request) -> dict[str, str | None]:
        return {"client_ip": _client_ip(request)}

    if trusted_hosts:
        app.add_middleware(
            ProxyHeadersMiddleware,
            trusted_hosts=trusted_hosts,
        )
    return app


# ``TestClient`` uses the literal string ``"testclient"`` as the socket
# peer host on every request — see ``starlette.testclient``. Configure
# the middleware to trust that exact host so the trusted-proxy path can
# be exercised through the test transport.
_TEST_CLIENT_PEER = "testclient"


def test_trusted_proxy_x_forwarded_for_is_honoured() -> None:
    """``X-Forwarded-For: 1.2.3.4`` from a trusted proxy resolves to ``1.2.3.4``.

    With the TestClient peer in ``trusted_hosts``, the middleware MUST
    rewrite ``scope["client"]`` to the forwarded value before
    ``_client_ip`` reads it.
    """
    app = _build_app(trusted_hosts=[_TEST_CLIENT_PEER])
    with TestClient(app) as client:
        response = client.get(
            "/peek",
            headers={"X-Forwarded-For": "1.2.3.4"},
        )

    assert response.status_code == 200
    assert response.json()["client_ip"] == "1.2.3.4"


def test_untrusted_proxy_x_forwarded_for_is_ignored() -> None:
    """An ``X-Forwarded-For`` from a proxy NOT in ``trusted_hosts`` is dropped.

    Without trust, the middleware MUST leave ``scope["client"]``
    untouched — ``_client_ip`` returns the unmodified socket peer.
    """
    # Trust a network the TestClient peer does NOT belong to so the
    # middleware refuses to rewrite the client tuple.
    app = _build_app(trusted_hosts=["10.0.0.0/8"])
    with TestClient(app) as client:
        response = client.get(
            "/peek",
            headers={"X-Forwarded-For": "1.2.3.4"},
        )

    assert response.status_code == 200
    # The middleware leaves the client tuple untouched; the spoofed
    # header is ignored. ``TestClient`` reports ``"testclient"`` as the
    # peer — the exact value doesn't matter, only that it is NOT the
    # spoofed ``1.2.3.4``.
    assert response.json()["client_ip"] != "1.2.3.4"
    assert response.json()["client_ip"] == _TEST_CLIENT_PEER


def test_no_middleware_returns_socket_peer() -> None:
    """Without the middleware installed, the helper returns the raw socket peer.

    Mirrors the dev / single-machine deployment where
    ``APP_TRUSTED_PROXY_IPS`` is empty — the production validator
    refuses that combination, but the dev path stays a no-op.
    """
    app = _build_app(trusted_hosts=[])
    with TestClient(app) as client:
        response = client.get(
            "/peek",
            headers={"X-Forwarded-For": "1.2.3.4"},
        )

    assert response.status_code == 200
    # No middleware means no rewrite, so the spoofed header is ignored.
    assert response.json()["client_ip"] != "1.2.3.4"
    assert response.json()["client_ip"] == _TEST_CLIENT_PEER
