"""Middleware that stamps ``X-Request-ID`` on every request/response.

The actual access log line is emitted by
:class:`~app_platform.api.middleware.access_log.AccessLogMiddleware`,
which is mounted INNER to this middleware so the contextvar is already
set by the time the line fires.
"""

from __future__ import annotations

import re
import uuid

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app_platform.observability.logging import REQUEST_ID_CONTEXT

_REQUEST_ID_RE = re.compile(r"^[a-zA-Z0-9\-_]{1,64}$")


class RequestContextMiddleware:
    """Inject ``X-Request-ID`` onto the request scope and the response.

    If the client supplies a valid ``X-Request-ID`` (alphanumeric/dash/
    underscore, max 64 chars), the value is reused; otherwise a random
    UUID4 is generated. Invalid client-supplied values are silently
    replaced to avoid echoing attacker-controlled strings into logs or
    response headers.

    The id is stamped onto :data:`REQUEST_ID_CONTEXT` for log
    correlation and onto ``scope["state"]["request_id"]`` for pure-ASGI
    middlewares that cannot synthesize a ``Request``.

    Implemented as a pure ASGI middleware (not ``BaseHTTPMiddleware``)
    so it does not turn pass-through responses into streaming responses
    — that matters because Starlette's ``GZipMiddleware`` only honours
    its ``minimum_size`` threshold when the inner response is
    non-streaming. See the comment block in
    :mod:`app_platform.api.app_factory`.
    """

    def __init__(self, app: ASGIApp) -> None:
        """Initialise the middleware."""
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Resolve/generate the request id and propagate it."""
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

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
        # middlewares (e.g. :class:`ContentSizeLimitMiddleware`,
        # :class:`AccessLogMiddleware`) can include it without
        # synthesizing a ``Request`` object.
        state = scope.get("state")
        if not isinstance(state, dict):
            state = {}
            scope["state"] = state
        state["request_id"] = request_id

        token = REQUEST_ID_CONTEXT.set(request_id)

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["X-Request-ID"] = request_id
            await send(message)

        try:
            await self._app(scope, receive, send_wrapper)
        finally:
            REQUEST_ID_CONTEXT.reset(token)
