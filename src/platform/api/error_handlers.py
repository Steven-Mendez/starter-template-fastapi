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

from src.platform.api.dependencies.container import DependencyContainerNotReadyError
from src.platform.api.error_handlers_app_exception import ApplicationHTTPException

PROBLEM_JSON = "application/problem+json"


def _status_title(code: int) -> str:
    try:
        return HTTPStatus(code).phrase
    except ValueError:
        return "Error"


def _http_exception_detail(exc: StarletteHTTPException) -> str | None:
    d = exc.detail
    if d is None:
        return None
    if isinstance(d, str):
        return d
    return json.dumps(jsonable_encoder(d))


def problem_json_response(
    *,
    status_code: int,
    request: Request,
    title: str | None = None,
    detail: str | None = None,
    type_uri: str = "about:blank",
    extra: dict[str, Any] | None = None,
) -> JSONResponse:
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
    )


def register_problem_details(app: FastAPI) -> None:
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
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return problem_json_response(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            request=request,
            title=_status_title(status.HTTP_422_UNPROCESSABLE_CONTENT),
            detail="Request validation failed",
            extra={"errors": exc.errors()},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.error(
            json.dumps(
                {
                    "request_id": getattr(request.state, "request_id", None),
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                    "error_type": type(exc).__name__,
                }
            ),
            exc_info=exc,
        )
        return problem_json_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            request=request,
            title=_status_title(status.HTTP_500_INTERNAL_SERVER_ERROR),
            detail="Internal Server Error",
        )
