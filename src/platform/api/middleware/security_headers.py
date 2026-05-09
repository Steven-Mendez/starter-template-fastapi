"""Middleware that injects security-hardening HTTP response headers."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add baseline security headers to every outgoing response.

    Headers added:
    - X-Content-Type-Options: nosniff  — prevent MIME-type sniffing
    - X-Frame-Options: DENY            — prevent clickjacking
    - Referrer-Policy: strict-origin-when-cross-origin
    - X-XSS-Protection: 0             — disabled; modern browsers rely on CSP
    - Strict-Transport-Security        — only when hsts=True (production)
    """

    def __init__(self, app: object, *, hsts: bool = False) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._hsts = hsts

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-XSS-Protection"] = "0"
        if self._hsts:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
        return response
