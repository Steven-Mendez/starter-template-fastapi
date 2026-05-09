"""Middleware for ``X-Request-ID`` and structured JSON access logs."""

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

_REQUEST_ID_RE = re.compile(r"^[a-zA-Z0-9\-_]{1,64}$")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Inject ``X-Request-ID`` and emit a JSON access log per request.

    If the client supplies a valid ``X-Request-ID`` (alphanumeric/dash/
    underscore, max 64 chars), the value is reused; otherwise a random
    UUID4 is generated. Invalid client-supplied values are silently
    replaced to avoid echoing attacker-controlled strings into logs or
    response headers.
    """

    def __init__(self, app: object, *, logger_name: str = "api.request") -> None:
        """Initialise the middleware with the logger name used for access logs."""
        super().__init__(app)  # type: ignore[arg-type]
        self._logger = logging.getLogger(logger_name)

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Handle the request, set request id, and emit one JSON access log."""
        started = time.perf_counter()
        raw_id = request.headers.get("X-Request-ID")
        if raw_id is not None and _REQUEST_ID_RE.match(raw_id):
            request_id = raw_id
        else:
            request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        self._logger.info(
            json.dumps(
                {
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": elapsed_ms,
                }
            )
        )
        return response
