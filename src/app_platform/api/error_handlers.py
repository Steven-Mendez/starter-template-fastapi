"""RFC 9457 Problem Details for HTTP APIs (application/problem+json)."""

from __future__ import annotations

import json
import logging
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app_platform.api.dependencies.container import DependencyContainerNotReadyError
from app_platform.api.error_handlers_app_exception import ApplicationHTTPException
from app_platform.api.problem_types import ProblemType
from app_platform.config.settings import AppSettings

PROBLEM_JSON = "application/problem+json"


def _status_title(code: int) -> str:
    """HTTP status phrase for ``code``, or ``"Error"`` if unknown."""
    try:
        return HTTPStatus(code).phrase
    except ValueError:
        return "Error"


def _http_exception_detail(exc: StarletteHTTPException) -> str | None:
    """Stringify HTTPException ``detail``, JSON-encoding non-string values."""
    d = exc.detail
    if d is None:
        return None
    if isinstance(d, str):
        return d
    return json.dumps(jsonable_encoder(d))


def pydantic_errors_to_violations(
    exc: RequestValidationError, *, include_input: bool
) -> list[dict[str, Any]]:
    """Translate Pydantic ``RequestValidationError`` entries into RFC 9457 violations.

    Each output entry exposes the public ``Violation`` shape documented in
    ``docs/api.md``:

    - ``loc: list[str | int]`` — canonical Pydantic location path.
    - ``type: str`` — stable Pydantic error type (e.g. ``"missing"``,
      ``"value_error"``).
    - ``msg: str`` — human-readable explanation.
    - ``input: object | None`` — the offending input value. Included only
      when ``include_input`` is True; the key is **omitted** entirely
      otherwise (typically in production) to avoid echoing secrets.

    The ``loc``, ``type``, and ``msg`` fields are identical across
    environments; only ``input`` is environment-gated.
    """
    violations: list[dict[str, Any]] = []
    for err in exc.errors():
        violation: dict[str, Any] = {
            "loc": list(err["loc"]),
            "type": err["type"],
            "msg": err["msg"],
        }
        if include_input:
            violation["input"] = err.get("input")
        violations.append(violation)
    return violations


def problem_json_response(
    *,
    status_code: int,
    request: Request,
    title: str | None = None,
    detail: str | None = None,
    type_uri: str = "about:blank",
    extra: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """Build an RFC 9457 Problem Details JSON response.

    The current request's ``request_id`` (set by
    :class:`RequestContextMiddleware`) is automatically included so
    error responses are easy to correlate with server-side logs.

    Args:
        status_code: HTTP status code to return.
        request: Incoming request, used to derive ``instance`` and ``request_id``.
        title: Human-readable summary; defaults to the status phrase.
        detail: Optional human-readable explanation of this specific occurrence.
        type_uri: URI identifying the problem type. ``"about:blank"`` is the
            RFC-recommended default when no specific type exists.
        extra: Optional extra fields merged into the payload (e.g. ``code``).
        headers: Optional response headers to attach. Used by the platform
            exception handlers to preserve ``WWW-Authenticate`` on 401 and
            ``Retry-After`` on 429, both of which travel on
            :attr:`HTTPException.headers`.

    Returns:
        A ``JSONResponse`` with ``application/problem+json`` media type.
    """
    payload: dict[str, Any] = {
        "type": type_uri,
        "title": title if title is not None else _status_title(status_code),
        "status": status_code,
        "instance": str(request.url),
    }
    if detail is not None:
        payload["detail"] = detail
    if extra:
        payload.update(extra)
    request_id = getattr(request.state, "request_id", None)
    if request_id is not None and "request_id" not in payload:
        payload["request_id"] = request_id
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder(payload),
        media_type=PROBLEM_JSON,
        headers=headers,
    )


def register_problem_details(app: FastAPI, settings: AppSettings) -> None:
    """Install the platform-wide exception handlers that produce RFC 9457 responses.

    Covers the dependency-container readiness error, application-level
    HTTP exceptions, generic Starlette HTTP exceptions, request-validation
    failures, and any otherwise-unhandled exception (which is logged
    structurally before being mapped to a 500).
    """
    logger = logging.getLogger("api.error")

    @app.exception_handler(DependencyContainerNotReadyError)
    async def dependency_container_not_ready_handler(
        request: Request, exc: DependencyContainerNotReadyError
    ) -> JSONResponse:
        return problem_json_response(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            request=request,
            detail=str(exc),
            type_uri="https://starter-template-fastapi.dev/problems/service-unavailable",
            extra={"code": "dependency_container_not_ready"},
        )

    @app.exception_handler(ApplicationHTTPException)
    async def application_http_exception_handler(
        request: Request, exc: ApplicationHTTPException
    ) -> JSONResponse:
        return problem_json_response(
            status_code=exc.status_code,
            request=request,
            detail=str(exc.detail),
            type_uri=exc.type_uri,
            extra={"code": exc.code},
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        detail_out = _http_exception_detail(exc)
        return problem_json_response(
            status_code=exc.status_code,
            request=request,
            detail=detail_out,
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        is_production = settings.environment == "production"
        violations = pydantic_errors_to_violations(exc, include_input=not is_production)
        if is_production:
            logger.warning(
                "Request validation failed",
                extra={
                    "path": request.url.path,
                    "validation_errors": exc.errors(),
                },
            )
        return problem_json_response(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            request=request,
            title=_status_title(status.HTTP_422_UNPROCESSABLE_CONTENT),
            detail=f"Validation failed: {len(violations)} field(s)",
            type_uri=ProblemType.VALIDATION_FAILED,
            extra={"violations": violations},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.error(
            "Unhandled exception",
            exc_info=exc,
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "error_type": type(exc).__name__,
            },
        )
        # Route through the configured error reporter so operators get a
        # paging signal (Sentry) or a structured WARN (logging fallback).
        # The reporter contract guarantees ``capture`` never raises, but
        # we defend in depth: any escape would re-enter this handler.
        reporter = getattr(request.app.state, "error_reporter", None)
        if reporter is not None:
            request_id = getattr(request.state, "request_id", None)
            principal_id = getattr(request.state, "principal_id", None)
            try:
                reporter.capture(
                    exc,
                    request_id=request_id,
                    path=str(request.url.path),
                    method=request.method,
                    principal_id=principal_id,
                )
            except Exception:  # pragma: no cover — defensive belt-and-braces
                logger.exception("event=error_reporter.unexpected_raise")
        return problem_json_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            request=request,
            title=_status_title(status.HTTP_500_INTERNAL_SERVER_ERROR),
            detail="Internal Server Error",
        )
