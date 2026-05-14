"""Middleware that injects security-hardening HTTP response headers."""

from __future__ import annotations

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

# Strict baseline policy applied to every JSON API response. A pure-JSON
# surface never needs to load any subresource, so ``default-src 'none'``
# is the strictest fallback that still permits the response itself.
# ``frame-ancestors 'none'`` is CSP's modern replacement for
# ``X-Frame-Options: DENY``.
_STRICT_CSP = "default-src 'none'; frame-ancestors 'none'"

# Relaxed policy applied only to the FastAPI docs surface (Swagger UI,
# ReDoc, and the OpenAPI schema endpoint). These pages load JS/CSS/font
# assets from the jsdelivr CDN and run inline scripts that Swagger UI
# requires; the strict policy above would break them. The override is
# gated on ``APP_ENABLE_DOCS=true`` at the call site, so it is never
# emitted in a production deployment that ships with docs disabled.
_DOCS_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "img-src 'self' data: https://fastapi.tiangolo.com; "
    "font-src 'self' https://cdn.jsdelivr.net; "
    "frame-ancestors 'none'"
)

_DOCS_PATHS: frozenset[str] = frozenset(
    {
        "/docs",
        "/docs/oauth2-redirect",
        "/redoc",
        "/openapi.json",
    }
)


class SecurityHeadersMiddleware:
    """Add baseline security headers to every outgoing response.

    Implemented as a pure ASGI middleware (not ``BaseHTTPMiddleware``)
    so it does not turn the response into a streaming response — that
    matters because Starlette's ``GZipMiddleware`` only honours its
    ``minimum_size`` threshold when the inner response is non-streaming.
    See the comment block in :mod:`app_platform.api.app_factory`.

    Headers added on every response:

    - ``Content-Security-Policy: default-src 'none'; frame-ancestors 'none'``
      — the strictest CSP that still permits the JSON response body.
      Overridden with a relaxed policy on the FastAPI docs routes when
      ``docs_enabled=True`` so Swagger UI / ReDoc can load CDN assets.
    - ``Referrer-Policy: no-referrer`` — strictest option; an API never
      needs to leak the source URL via the ``Referer`` request header.
    - ``X-Content-Type-Options: nosniff`` — disables MIME-sniffing on
      JSON responses.
    - ``Permissions-Policy: ()`` — empty policy denies every browser
      feature (camera, microphone, geolocation, etc.). JSON responses
      never need any of them.
    - ``Strict-Transport-Security`` — only when ``hsts=True``
      (production); the same one-year + preload value used previously.

    Response headers stripped on every response if present:

    - ``Server`` — leaks stack identity without operational value.
    - ``X-Powered-By`` — same rationale.
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        hsts: bool = False,
        docs_enabled: bool = False,
    ) -> None:
        self._app = app
        self._hsts = hsts
        self._docs_enabled = docs_enabled

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        path = scope.get("path", "")
        csp = _DOCS_CSP if self._docs_enabled and path in _DOCS_PATHS else _STRICT_CSP

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["Content-Security-Policy"] = csp
                headers["Referrer-Policy"] = "no-referrer"
                headers["X-Content-Type-Options"] = "nosniff"
                headers["Permissions-Policy"] = "()"
                if self._hsts:
                    headers["Strict-Transport-Security"] = (
                        "max-age=31536000; includeSubDomains; preload"
                    )
                # Strip stack-identity headers if any upstream layer
                # (uvicorn, a reverse proxy, a future feature) set them.
                if "server" in headers:
                    del headers["server"]
                if "x-powered-by" in headers:
                    del headers["x-powered-by"]
            await send(message)

        await self._app(scope, receive, send_wrapper)
