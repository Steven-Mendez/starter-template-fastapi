"""Middleware that injects security-hardening HTTP response headers."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add baseline security headers to every outgoing response.

    Headers added:
    - X-Content-Type-Options: nosniff   — prevent MIME-type sniffing
    - X-Frame-Options: DENY             — prevent clickjacking
    - Referrer-Policy: strict-origin-when-cross-origin
    - X-XSS-Protection: 0               — disabled; modern browsers rely on CSP
    - Content-Security-Policy           — default-src 'none' for pure-JSON APIs
    - Permissions-Policy                — disable camera/mic/geolocation/etc.
    - Cross-Origin-Opener-Policy        — same-origin (process isolation)
    - Cross-Origin-Resource-Policy      — same-origin (CORB-style protection)
    - Strict-Transport-Security         — only when hsts=True (production)
    """

    # Disable every browser feature exposed via Permissions-Policy. JSON
    # APIs never need these capabilities; turning them off prevents a
    # cross-origin embedder from invoking them on the API origin.
    _PERMISSIONS_POLICY = ", ".join(
        f"{feature}=()"
        for feature in (
            "accelerometer",
            "ambient-light-sensor",
            "autoplay",
            "battery",
            "camera",
            "display-capture",
            "fullscreen",
            "geolocation",
            "gyroscope",
            "magnetometer",
            "microphone",
            "midi",
            "payment",
            "picture-in-picture",
            "publickey-credentials-get",
            "screen-wake-lock",
            "sync-xhr",
            "usb",
            "xr-spatial-tracking",
        )
    )

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
        response.headers["Content-Security-Policy"] = "default-src 'none'"
        response.headers["Permissions-Policy"] = self._PERMISSIONS_POLICY
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        if self._hsts:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )
        return response
