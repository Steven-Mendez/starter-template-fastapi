"""ASGI middleware that emits one structured access log per HTTP request.

This middleware is mounted INNER to
:class:`~app_platform.api.middleware.request_context.RequestContextMiddleware`
so the per-request id contextvar is already populated by the time the
access log fires. The line carries ``method``, ``path``, ``status_code``,
``duration_ms``, and ``request_id``.

The dedicated middleware replaces uvicorn's built-in access log: that
record runs OUTSIDE the request-context window and therefore always
emits ``request_id=null``. Disabling uvicorn's access log is done in
:mod:`app_platform.observability.logging`.

Implemented as a pure ASGI middleware (not ``BaseHTTPMiddleware``) so
it does not turn pass-through responses into streaming responses — the
same constraint that applies to the other custom middleware in this
codebase.
"""

from __future__ import annotations

import logging
import time

from starlette.types import ASGIApp, Message, Receive, Scope, Send


class AccessLogMiddleware:
    """Emit a JSON access log per HTTP request."""

    def __init__(self, app: ASGIApp, *, logger_name: str = "api.access") -> None:
        """Initialise with the logger name used for access records."""
        self._app = app
        self._logger = logging.getLogger(logger_name)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Wrap ``send`` so we can record the response status, then log."""
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        started = time.perf_counter()
        status_holder: dict[str, int] = {"status": 0}

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                status_holder["status"] = int(message["status"])
            await send(message)

        try:
            await self._app(scope, receive, send_wrapper)
        finally:
            elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
            # ``RequestContextMiddleware`` stamps the id onto
            # ``scope["state"]`` for pure-ASGI middlewares that cannot
            # synthesize a ``Request`` object. The contextvar carries
            # the same value to the JSON formatter via
            # :class:`RequestIdFilter`.
            state = scope.get("state")
            request_id = state.get("request_id") if isinstance(state, dict) else None
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
