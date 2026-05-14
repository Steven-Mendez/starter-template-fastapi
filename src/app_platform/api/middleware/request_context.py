"""Middleware for ``X-Request-ID`` and structured JSON access logs."""

from __future__ import annotations

import logging
import re
import time
import uuid

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app_platform.observability.logging import REQUEST_ID_CONTEXT

_REQUEST_ID_RE = re.compile(r"^[a-zA-Z0-9\-_]{1,64}$")


class RequestContextMiddleware:
    """Inject ``X-Request-ID`` and emit a JSON access log per request.

    If the client supplies a valid ``X-Request-ID`` (alphanumeric/dash/
    underscore, max 64 chars), the value is reused; otherwise a random
    UUID4 is generated. Invalid client-supplied values are silently
    replaced to avoid echoing attacker-controlled strings into logs or
    response headers.

    Implemented as a pure ASGI middleware (not ``BaseHTTPMiddleware``)
    so it does not turn pass-through responses into streaming responses
    — that matters because Starlette's ``GZipMiddleware`` only honours
    its ``minimum_size`` threshold when the inner response is
    non-streaming. See the comment block in
    :mod:`app_platform.api.app_factory`.
    """

    def __init__(self, app: ASGIApp, *, logger_name: str = "api.request") -> None:
        """Initialise the middleware with the logger name used for access logs."""
        self._app = app
        self._logger = logging.getLogger(logger_name)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Handle the request, set request id, and emit one JSON access log."""
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        started = time.perf_counter()

        # Resolve / generate the request id.
        raw_id: str | None = None
        for key, value in scope.get("headers", []):
            if key == b"x-request-id":
                raw_id = value.decode("latin-1")
                break
        if raw_id is not None and _REQUEST_ID_RE.match(raw_id):
            request_id = raw_id
        else:
            request_id = str(uuid.uuid4())

        # Expose on ``scope["state"]`` so Starlette/FastAPI handlers can
        # read it via ``request.state.request_id``, and so pure-ASGI
        # middlewares (e.g. :class:`ContentSizeLimitMiddleware`) that
        # short-circuit can include it in their problem bodies.
        state = scope.get("state")
        if not isinstance(state, dict):
            state = {}
            scope["state"] = state
        state["request_id"] = request_id

        token = REQUEST_ID_CONTEXT.set(request_id)
        status_holder: dict[str, int] = {"status": 0}

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                status_holder["status"] = int(message["status"])
                headers = MutableHeaders(scope=message)
                headers["X-Request-ID"] = request_id
            await send(message)

        try:
            await self._app(scope, receive, send_wrapper)
            elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
            self._logger.info(
                "HTTP request completed",
                extra={
                    "request_id": request_id,
                    "method": scope.get("method", ""),
                    "path": scope.get("path", ""),
                    "status_code": status_holder["status"],
                    "duration_ms": elapsed_ms,
                },
            )
        finally:
            REQUEST_ID_CONTEXT.reset(token)
