"""Middleware that rejects requests whose Content-Length exceeds a limit."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


class ContentSizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject incoming requests whose Content-Length exceeds the configured limit.

    Only checks the Content-Length header; it does not buffer and measure the
    body itself. Clients that omit Content-Length are not rejected here.

    Args:
        max_bytes: Maximum allowed Content-Length in bytes. Default 4 MiB.
    """

    def __init__(self, app: object, *, max_bytes: int = 4 * 1024 * 1024) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._max_bytes = max_bytes

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                size = int(content_length)
            except ValueError:
                return JSONResponse(
                    status_code=400,
                    content={"detail": "Invalid Content-Length header"},
                )
            if size > self._max_bytes:
                return JSONResponse(
                    status_code=413,
                    content={"detail": "Request body too large"},
                )
        return await call_next(request)
