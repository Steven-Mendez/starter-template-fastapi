"""Middleware that rejects oversized or unmeasurable request bodies."""

from __future__ import annotations

import json

from starlette.types import ASGIApp, Message, Receive, Scope, Send

# Media type for the bodies we return on reject. Matches the shape used
# by :mod:`app_platform.api.error_handlers` so clients can rely on a
# single content-type for every 4xx response.
_PROBLEM_JSON = "application/problem+json"


def _build_url(scope: Scope) -> str:
    """Reconstruct the request URL from the ASGI scope (best-effort)."""
    scheme = str(scope.get("scheme", "http"))
    server = scope.get("server") or ("", None)
    host_header: str | None = None
    for key, value in scope.get("headers", []):
        if key == b"host":
            host_header = value.decode("latin-1")
            break
    if host_header is not None:
        netloc = host_header
    else:
        host, port = server
        netloc = f"{host}:{port}" if port else str(host)
    path = scope.get("path", "")
    raw_query = scope.get("query_string", b"")
    query = f"?{raw_query.decode('latin-1')}" if raw_query else ""
    return f"{scheme}://{netloc}{path}{query}"


def _get_header(scope: Scope, name: bytes) -> str | None:
    for key, value in scope.get("headers", []):
        if key == name:
            decoded: str = bytes(value).decode("latin-1")
            return decoded
    return None


def _get_request_id(scope: Scope) -> str | None:
    """Return the request id stamped onto the scope by RequestContextMiddleware.

    The id is also exposed on ``request.state.request_id`` for handlers
    that build a Starlette/FastAPI ``Request`` object; the scope is the
    pure-ASGI canonical location.
    """
    state = scope.get("state")
    if isinstance(state, dict):
        rid = state.get("request_id")
        if isinstance(rid, str):
            return rid
    return None


class ContentSizeLimitMiddleware:
    """Reject requests that are too large or have an unmeasurable body.

    Two checks fire before the inner handler ever sees the request:

    1. ``Content-Length`` is present and exceeds ``max_bytes`` →
       ``413 Payload Too Large``.
    2. ``Transfer-Encoding`` contains ``chunked`` AND ``Content-Length``
       is absent → ``411 Length Required``. Without a declared length we
       cannot bound the body here without buffering, so we refuse the
       request outright. This closes the long-standing footgun where any
       HTTP/1.1 client could stream gigabytes through by omitting
       ``Content-Length``.

    Implemented as a pure ASGI middleware (not ``BaseHTTPMiddleware``)
    so it does not turn pass-through responses into streaming responses
    — that matters because Starlette's ``GZipMiddleware`` only honours
    its ``minimum_size`` threshold when the inner response is
    non-streaming. See the comment block in
    :mod:`app_platform.api.app_factory`.

    Args:
        max_bytes: Maximum allowed Content-Length in bytes. Default 4 MiB.
    """

    def __init__(self, app: ASGIApp, *, max_bytes: int = 4 * 1024 * 1024) -> None:
        self._app = app
        self._max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        content_length = _get_header(scope, b"content-length")
        if content_length is not None:
            try:
                size = int(content_length)
            except ValueError:
                await self._send_problem(
                    scope,
                    send,
                    status_code=400,
                    title="Bad Request",
                    detail="Invalid Content-Length header",
                )
                return
            if size > self._max_bytes:
                await self._send_problem(
                    scope,
                    send,
                    status_code=413,
                    title="Content Too Large",
                    detail="Request body too large",
                )
                return
        else:
            # No Content-Length supplied. If the client is streaming with
            # ``Transfer-Encoding: chunked`` we have no upper bound on
            # the body size here; reject with 411 Length Required per
            # RFC 9110 §10.4.13.
            transfer_encoding = _get_header(scope, b"transfer-encoding") or ""
            if "chunked" in transfer_encoding.lower():
                await self._send_problem(
                    scope,
                    send,
                    status_code=411,
                    title="Length Required",
                    detail=(
                        "Requests using Transfer-Encoding: chunked "
                        "must include a Content-Length header."
                    ),
                )
                return
        await self._app(scope, receive, send)

    async def _send_problem(
        self,
        scope: Scope,
        send: Send,
        *,
        status_code: int,
        title: str,
        detail: str,
    ) -> None:
        payload: dict[str, object] = {
            "type": "about:blank",
            "title": title,
            "status": status_code,
            "detail": detail,
            "instance": _build_url(scope),
        }
        request_id = _get_request_id(scope)
        if request_id is not None:
            payload["request_id"] = request_id
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        headers: list[tuple[bytes, bytes]] = [
            (b"content-type", _PROBLEM_JSON.encode("ascii")),
            (b"content-length", str(len(body)).encode("ascii")),
        ]
        start: Message = {
            "type": "http.response.start",
            "status": status_code,
            "headers": headers,
        }
        await send(start)
        await send({"type": "http.response.body", "body": body, "more_body": False})
