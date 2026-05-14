"""Header-preservation contract for the platform Problem Details handlers.

The generic ``http_exception_handler`` and its siblings construct a fresh
``JSONResponse``; before this change ``HTTPException.headers`` was silently
dropped, so ``WWW-Authenticate: Bearer`` (set on 401s) and ``Retry-After``
(set on 429s) never reached the client. These tests pin the behavior so it
cannot regress.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

import pytest
from fastapi import FastAPI, HTTPException, status
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app_platform.api.app_factory import build_fastapi_app
from app_platform.api.dependencies.container import set_app_container
from app_platform.api.error_handlers_app_exception import ApplicationHTTPException
from app_platform.config.settings import AppSettings

pytestmark = pytest.mark.unit


@dataclass(frozen=True, slots=True)
class _Container:
    settings: AppSettings


def _build(settings: AppSettings) -> FastAPI:
    app = build_fastapi_app(settings)

    @app.get("/__401_bearer")
    def _bearer_challenge() -> dict[str, str]:
        # Mirrors what ``_credentials_exception`` raises on missing auth.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    @app.get("/__429_retry_after")
    def _retry_after() -> dict[str, str]:
        raise ApplicationHTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            code="rate_limit_exceeded",
            type_uri="urn:problem:auth:rate-limited",
            headers={"Retry-After": "42"},
        )

    @app.get("/__400_no_headers")
    def _no_headers() -> dict[str, str]:
        # Bare HTTPException with no headers — handler must not crash and
        # must still attach the request_id from upstream middleware.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="bad",
        )

    @asynccontextmanager
    async def lifespan(lifespan_app: FastAPI):  # type: ignore[no-untyped-def]
        set_app_container(lifespan_app, _Container(settings=settings))
        yield
        lifespan_app.state.container = None

    app.router.lifespan_context = lifespan
    return app


@pytest.fixture
def client(test_settings: AppSettings) -> Iterator[TestClient]:
    with TestClient(_build(test_settings)) as c:
        yield c


def test_401_response_carries_www_authenticate_bearer(client: TestClient) -> None:
    """RFC 7235: a 401 challenge MUST include a ``WWW-Authenticate`` header."""
    resp = client.get("/__401_bearer")
    assert resp.status_code == 401
    assert resp.headers.get("WWW-Authenticate") == "Bearer"


def test_401_response_carries_request_id(client: TestClient) -> None:
    """``RequestContextMiddleware`` sets ``X-Request-ID`` on every response."""
    resp = client.get("/__401_bearer")
    assert resp.status_code == 401
    request_id = resp.headers.get("X-Request-ID")
    assert request_id is not None
    assert request_id != ""


def test_429_response_carries_retry_after(client: TestClient) -> None:
    """RFC 7231 §7.1.3: a 429 SHOULD include ``Retry-After``; ours does."""
    resp = client.get("/__429_retry_after")
    assert resp.status_code == 429
    retry_after = resp.headers.get("Retry-After")
    assert retry_after is not None
    parsed = int(retry_after)
    assert parsed > 0


def test_error_response_without_headers_still_renders(client: TestClient) -> None:
    """``getattr(exc, "headers", None)`` falls through to ``None`` without error."""
    resp = client.get("/__400_no_headers")
    assert resp.status_code == 400
    # Upstream middleware still adds the request id.
    assert resp.headers.get("X-Request-ID")
    # And we do not invent any other header.
    assert "WWW-Authenticate" not in resp.headers
    assert "Retry-After" not in resp.headers


def test_content_language_survives_error_response(
    test_settings: AppSettings,
) -> None:
    """A ``Content-Language`` set by upstream middleware must reach the client.

    The Problem Details handler rebuilds the response body but only sets the
    response's own ``Content-Type``. Middleware that runs *around* the handler
    (i.e. registered after the routing layer in Starlette's middleware stack)
    can layer ``Content-Language`` on top of the resulting response, and that
    header must survive.
    """
    app = _build(test_settings)

    class _ContentLanguageMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
            response: Response = await call_next(request)
            response.headers["Content-Language"] = "en-US"
            return response

    app.add_middleware(_ContentLanguageMiddleware)

    with TestClient(app) as c:
        resp = c.get("/__400_no_headers")
    assert resp.status_code == 400
    assert resp.headers.get("Content-Language") == "en-US"
