"""RFC 9457 Problem Details for HTTP APIs (application/problem+json)."""

from __future__ import annotations

import json
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

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
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder(payload),
        media_type=PROBLEM_JSON,
    )


def register_problem_details(app: FastAPI) -> None:
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
