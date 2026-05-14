"""Tests for the hardened HTTP middleware stack.

Covers the behaviors introduced by
``openspec/changes/harden-http-middleware-stack``:

- GZip compresses JSON responses >= 1 KiB when the client advertises gzip.
- CORS preflight enumerates allowed methods/headers and exposes
  ``X-Request-ID`` / ``Retry-After`` to JS.
- :class:`ContentSizeLimitMiddleware` rejects ``Transfer-Encoding: chunked``
  without a ``Content-Length`` with a 411 Problem Details body.
"""

from __future__ import annotations

import asyncio
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app_platform.api.app_factory import build_fastapi_app
from app_platform.config.settings import AppSettings

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_app(settings: AppSettings) -> FastAPI:
    """Build the platform app with a few endpoints suitable for these tests."""
    app = build_fastapi_app(settings)

    @app.get("/__big_json")
    def _big_json() -> dict[str, list[dict[str, str]]]:
        # Returns ~5 KiB of structured JSON so the response is well above
        # the 1 KiB GZip threshold.
        rows = [{"id": f"row-{i:04d}", "value": "x" * 64} for i in range(64)]
        return {"rows": rows}

    @app.post("/__echo")
    def _echo(payload: dict[str, str]) -> dict[str, str]:
        return payload

    return app


def _credentialed_settings(test_settings: AppSettings) -> AppSettings:
    """Settings with a concrete CORS origin so the credentialed branch runs."""
    return test_settings.model_copy(
        update={
            "cors_origins": ["https://web.example.com"],
        }
    )


# ---------------------------------------------------------------------------
# 5.1 GZip
# ---------------------------------------------------------------------------


def test_gzip_compresses_large_json_when_client_accepts_gzip(
    test_settings: AppSettings,
) -> None:
    """A >1 KiB JSON body is gzipped when ``Accept-Encoding: gzip`` is sent."""
    with TestClient(_build_app(test_settings)) as c:
        resp = c.get("/__big_json", headers={"Accept-Encoding": "gzip"})
    assert resp.status_code == 200
    assert resp.headers.get("content-encoding") == "gzip"
    # ``resp.content`` is transparently decompressed by httpx; verify the
    # body parses back into the original JSON structure.
    parsed = json.loads(resp.content)
    assert "rows" in parsed
    assert len(parsed["rows"]) == 64


def test_gzip_skipped_when_client_does_not_accept_gzip(
    test_settings: AppSettings,
) -> None:
    """A client without ``Accept-Encoding: gzip`` receives an uncompressed body."""
    with TestClient(_build_app(test_settings)) as c:
        resp = c.get("/__big_json", headers={"Accept-Encoding": "identity"})
    assert resp.status_code == 200
    assert resp.headers.get("content-encoding") != "gzip"


# ---------------------------------------------------------------------------
# 5.2 CORS preflight: enumerated methods
# ---------------------------------------------------------------------------


def test_cors_preflight_allows_post(test_settings: AppSettings) -> None:
    """``POST`` is in the explicit allow-list and preflight succeeds."""
    settings = _credentialed_settings(test_settings)
    with TestClient(_build_app(settings)) as c:
        resp = c.options(
            "/__echo",
            headers={
                "Origin": "https://web.example.com",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type",
            },
        )
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == "https://web.example.com"
    allow_methods = resp.headers["access-control-allow-methods"]
    assert "POST" in allow_methods


def test_cors_preflight_rejects_put(test_settings: AppSettings) -> None:
    """``PUT`` is not in the enumerated allow-list — preflight is refused."""
    settings = _credentialed_settings(test_settings)
    with TestClient(_build_app(settings)) as c:
        resp = c.options(
            "/__echo",
            headers={
                "Origin": "https://web.example.com",
                "Access-Control-Request-Method": "PUT",
                "Access-Control-Request-Headers": "Content-Type",
            },
        )
    # Starlette's CORSMiddleware returns 400 with body
    # "Disallowed CORS method" when the requested method is not allowed.
    assert resp.status_code == 400
    # The 400 body identifies the disallowed method as the reason.
    assert "method" in resp.text.lower()
    # And ``PUT`` is NOT in the enumerated allow-methods response header
    # — Starlette echoes back only what we configured.
    allow_methods = resp.headers.get("access-control-allow-methods", "")
    assert "PUT" not in allow_methods


def test_cors_preflight_rejects_unlisted_header(test_settings: AppSettings) -> None:
    """A header outside the enumerated allow-list also fails preflight."""
    settings = _credentialed_settings(test_settings)
    with TestClient(_build_app(settings)) as c:
        resp = c.options(
            "/__echo",
            headers={
                "Origin": "https://web.example.com",
                "Access-Control-Request-Method": "POST",
                # ``X-Custom-Probe`` is not in the allow-list.
                "Access-Control-Request-Headers": "X-Custom-Probe",
            },
        )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# 5.4 expose_headers
# ---------------------------------------------------------------------------


def test_cross_origin_response_exposes_request_id_and_retry_after(
    test_settings: AppSettings,
) -> None:
    """``Access-Control-Expose-Headers`` lists ``X-Request-ID`` and ``Retry-After``."""
    settings = _credentialed_settings(test_settings)
    with TestClient(_build_app(settings)) as c:
        resp = c.post(
            "/__echo",
            json={"hello": "world"},
            headers={"Origin": "https://web.example.com"},
        )
    assert resp.status_code == 200
    expose = resp.headers.get("access-control-expose-headers", "")
    # Header value is a comma-separated list (Starlette joins them).
    parts = {p.strip() for p in expose.split(",")}
    assert "X-Request-ID" in parts
    assert "Retry-After" in parts


# ---------------------------------------------------------------------------
# 5.3 Content-size: chunked without Content-Length → 411
# ---------------------------------------------------------------------------


async def _drive_asgi(
    app: FastAPI,
    method: str,
    path: str,
    raw_headers: list[tuple[bytes, bytes]],
    body: bytes,
) -> tuple[int, dict[str, str], bytes]:
    """Invoke an ASGI app directly with full control over the header list.

    Drives the ``http`` scope by hand because :class:`fastapi.testclient.TestClient`
    (and httpx more generally) normalize / rewrite header values such as
    ``Content-Length`` and ``Transfer-Encoding``. To test the chunked-no-length
    branch we need to deliver the exact header list the middleware would see
    from a real client speaking HTTP/1.1 with ``Transfer-Encoding: chunked``.
    """
    scope: dict[str, object] = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("ascii"),
        "query_string": b"",
        "headers": [(b"host", b"testserver"), *raw_headers],
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
    }

    sent_body = body
    sent = {"done": False}

    async def receive() -> dict[str, object]:
        if sent["done"]:
            return {"type": "http.disconnect"}
        sent["done"] = True
        return {"type": "http.request", "body": sent_body, "more_body": False}

    status_code = 0
    headers_out: dict[str, str] = {}
    body_chunks: list[bytes] = []

    async def send(message: dict[str, object]) -> None:
        nonlocal status_code
        if message["type"] == "http.response.start":
            status_raw = message["status"]
            assert isinstance(status_raw, int)
            status_code = status_raw
            raw_headers_out = message.get("headers", [])
            assert isinstance(raw_headers_out, list)
            for k, v in raw_headers_out:
                headers_out[k.decode("latin-1").lower()] = v.decode("latin-1")
        elif message["type"] == "http.response.body":
            chunk = message.get("body", b"")
            if isinstance(chunk, bytes):
                body_chunks.append(chunk)

    await app(scope, receive, send)  # type: ignore[arg-type]
    return status_code, headers_out, b"".join(body_chunks)


def test_chunked_post_without_content_length_returns_411(
    test_settings: AppSettings,
) -> None:
    """``Transfer-Encoding: chunked`` with no ``Content-Length`` is rejected."""
    app = _build_app(test_settings)
    status, headers, body = asyncio.run(
        _drive_asgi(
            app,
            "POST",
            "/__echo",
            raw_headers=[
                (b"transfer-encoding", b"chunked"),
                (b"content-type", b"application/json"),
            ],
            body=b'{"hello":"world"}',
        )
    )
    assert status == 411
    payload = json.loads(body)
    assert payload["status"] == 411
    assert payload["title"] == "Length Required"
    # Problem Details media type.
    assert headers.get("content-type", "").startswith("application/problem+json")


def test_chunked_post_with_content_length_passes_through(
    test_settings: AppSettings,
) -> None:
    """A chunked request that ALSO carries Content-Length is not rejected."""
    app = _build_app(test_settings)
    payload_bytes = b'{"hello":"world"}'
    status, _headers, body = asyncio.run(
        _drive_asgi(
            app,
            "POST",
            "/__echo",
            raw_headers=[
                (b"transfer-encoding", b"chunked"),
                (b"content-length", str(len(payload_bytes)).encode("ascii")),
                (b"content-type", b"application/json"),
            ],
            body=payload_bytes,
        )
    )
    # Should reach the inner handler; Content-Length is present so the 411
    # branch does not fire.
    assert status == 200
    assert json.loads(body) == {"hello": "world"}


def test_post_without_transfer_encoding_or_content_length_passes_through(
    test_settings: AppSettings,
) -> None:
    """Requests without either header are accepted (e.g. GETs and empty POSTs)."""
    app = _build_app(test_settings)
    with TestClient(app) as c:
        # A regular POST will have Content-Length set by httpx automatically;
        # we simply confirm the middleware does not over-block ordinary traffic.
        resp = c.post("/__echo", json={"hello": "world"})
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Regression: SecurityHeaders is OUTER to ContentSizeLimit, so its strict
# baseline headers are attached to ContentSizeLimit's 411/413/400
# short-circuit responses too. Previously SecurityHeaders sat INSIDE
# ContentSizeLimit and those short-circuits shipped without CSP /
# Referrer-Policy / X-Content-Type-Options / Permissions-Policy.
# ---------------------------------------------------------------------------


_STRICT_CSP = "default-src 'none'; frame-ancestors 'none'"


def test_security_headers_present_on_content_size_limit_411(
    test_settings: AppSettings,
) -> None:
    """The 411 short-circuit response carries the strict baseline headers."""
    app = _build_app(test_settings)
    status, headers, _body = asyncio.run(
        _drive_asgi(
            app,
            "POST",
            "/__echo",
            raw_headers=[
                (b"transfer-encoding", b"chunked"),
                (b"content-type", b"application/json"),
            ],
            body=b'{"hello":"world"}',
        )
    )
    assert status == 411
    assert headers.get("content-security-policy") == _STRICT_CSP
    assert headers.get("referrer-policy") == "no-referrer"
    assert headers.get("x-content-type-options") == "nosniff"
    assert headers.get("permissions-policy") == "()"


def test_security_headers_present_on_content_size_limit_413(
    test_settings: AppSettings,
) -> None:
    """The 413 short-circuit response carries the strict baseline headers."""
    app = _build_app(test_settings)
    # Settings default ``max_request_bytes`` is 4 MiB; declare a much larger
    # Content-Length so the 413 branch fires.
    huge = str(10 * 1024 * 1024).encode("ascii")
    status, headers, _body = asyncio.run(
        _drive_asgi(
            app,
            "POST",
            "/__echo",
            raw_headers=[
                (b"content-length", huge),
                (b"content-type", b"application/json"),
            ],
            body=b"",
        )
    )
    assert status == 413
    assert headers.get("content-security-policy") == _STRICT_CSP
    assert headers.get("referrer-policy") == "no-referrer"
    assert headers.get("x-content-type-options") == "nosniff"
    assert headers.get("permissions-policy") == "()"


def test_security_headers_present_on_content_size_limit_400(
    test_settings: AppSettings,
) -> None:
    """The 400 short-circuit (invalid Content-Length) carries the baseline headers."""
    app = _build_app(test_settings)
    status, headers, _body = asyncio.run(
        _drive_asgi(
            app,
            "POST",
            "/__echo",
            raw_headers=[
                (b"content-length", b"not-an-integer"),
                (b"content-type", b"application/json"),
            ],
            body=b"",
        )
    )
    assert status == 400
    assert headers.get("content-security-policy") == _STRICT_CSP
    assert headers.get("referrer-policy") == "no-referrer"
    assert headers.get("x-content-type-options") == "nosniff"
    assert headers.get("permissions-policy") == "()"


# ---------------------------------------------------------------------------
# Regression: middleware registration order. Asserts the runtime
# outer→inner ordering of CORS, TrustedHost, SecurityHeaders, GZip,
# ContentSizeLimit, RequestContext directly from ``app.user_middleware``.
# Starlette stores the list in OUTER → INNER order.
# ---------------------------------------------------------------------------


def test_middleware_registration_order_is_stable(test_settings: AppSettings) -> None:
    """``app.user_middleware`` lists middleware OUTER → INNER as documented."""
    from fastapi.middleware.cors import CORSMiddleware
    from starlette.middleware.gzip import GZipMiddleware
    from starlette.middleware.trustedhost import TrustedHostMiddleware

    from app_platform.api.middleware.content_size_limit import (
        ContentSizeLimitMiddleware,
    )
    from app_platform.api.middleware.request_context import RequestContextMiddleware
    from app_platform.api.middleware.security_headers import SecurityHeadersMiddleware

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
    app = build_fastapi_app(settings)
    class_names = [getattr(m.cls, "__name__", str(m.cls)) for m in app.user_middleware]
    expected_order = [
        CORSMiddleware.__name__,
        TrustedHostMiddleware.__name__,
        SecurityHeadersMiddleware.__name__,
        GZipMiddleware.__name__,
        ContentSizeLimitMiddleware.__name__,
        RequestContextMiddleware.__name__,
    ]
    # All expected classes are present.
    for name in expected_order:
        assert name in class_names, f"{name} missing from middleware stack"
    # And in the documented relative order (no other middleware is
    # registered, but using indices keeps the assertion robust to
    # future additions).
    indices = [class_names.index(name) for name in expected_order]
    assert indices == sorted(indices), f"middleware order broken: {class_names}"


def test_compressed_response_carries_csp_and_request_id(
    test_settings: AppSettings,
) -> None:
    """A >1 KiB gzipped response still carries the strict CSP and X-Request-ID."""
    with TestClient(_build_app(test_settings)) as c:
        resp = c.get("/__big_json", headers={"Accept-Encoding": "gzip"})
    assert resp.status_code == 200
    assert resp.headers.get("content-encoding") == "gzip"
    assert resp.headers.get("content-security-policy") == _STRICT_CSP
    request_id = resp.headers.get("x-request-id", "")
    assert request_id, "X-Request-ID must be non-empty on compressed responses"


def test_gzip_skipped_for_small_response_under_minimum_size(
    test_settings: AppSettings,
) -> None:
    """A <1 KiB JSON body is NOT gzipped even when ``Accept-Encoding: gzip`` is sent.

    Regression for the original QA finding: when the inner middlewares
    were ``BaseHTTPMiddleware``-derived they returned streaming
    responses, defeating GZip's ``minimum_size=1024`` threshold and
    causing every tiny response to be compressed. After converting
    SecurityHeaders, RequestContext, and ContentSizeLimit to pure ASGI
    middlewares, GZip can see the response is non-streaming and honour
    the threshold.
    """
    app = build_fastapi_app(test_settings)

    @app.get("/__tiny")
    def _tiny() -> dict[str, str]:
        return {"ok": "yes"}

    with TestClient(app) as c:
        resp = c.get("/__tiny", headers={"Accept-Encoding": "gzip"})
    assert resp.status_code == 200
    assert resp.headers.get("content-encoding") != "gzip"
    assert json.loads(resp.content) == {"ok": "yes"}


def test_chunked_no_length_problem_body_includes_request_id_when_set(
    test_settings: AppSettings,
) -> None:
    """If RequestContext has stamped a request id, the 411 body includes it.

    With the documented chain (ContentSizeLimit is OUTER to
    RequestContext) the id will normally NOT be present on
    short-circuits; this test pre-populates ``scope["state"]`` to verify
    the propagation path works when an outer layer has populated it.
    """
    from app_platform.api.middleware.content_size_limit import (
        ContentSizeLimitMiddleware,
    )

    async def _ok_app(
        scope: dict[str, object],
        receive: object,
        send: object,
    ) -> None:  # pragma: no cover - never reached in this test
        raise AssertionError("inner app must not be invoked")

    middleware = ContentSizeLimitMiddleware(_ok_app, max_bytes=4 * 1024 * 1024)  # type: ignore[arg-type]

    sent_messages: list[dict[str, object]] = []

    async def send(message: dict[str, object]) -> None:
        sent_messages.append(message)

    async def receive() -> dict[str, object]:
        return {"type": "http.request", "body": b"", "more_body": False}

    scope: dict[str, object] = {
        "type": "http",
        "method": "POST",
        "scheme": "http",
        "path": "/x",
        "raw_path": b"/x",
        "query_string": b"",
        "headers": [
            (b"host", b"testserver"),
            (b"transfer-encoding", b"chunked"),
        ],
        "state": {"request_id": "deterministic-id-123"},
    }

    asyncio.run(middleware(scope, receive, send))  # type: ignore[arg-type]
    assert sent_messages[0]["type"] == "http.response.start"
    assert sent_messages[0]["status"] == 411
    body_msg = sent_messages[1]
    body_bytes = body_msg["body"]
    assert isinstance(body_bytes, bytes)
    payload = json.loads(body_bytes)
    assert payload["request_id"] == "deterministic-id-123"
