"""Wiring helpers for the authorization feature.

Exposes:

* ``attach_authorization_container``: publishes the authorization port
  on ``app.state.authorization`` so the platform-level
  ``require_authorization`` dependency can read it without importing
  from any feature.
* ``register_authorization_error_handlers``: maps domain authorization
  errors raised inside ``AuthorizationPort.check`` (typically by the
  platform-level ``require_authorization`` dependency on a feature's
  routes) to Problem Details responses.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app_platform.api.problem_types import ProblemType
from features.authorization.application.errors import (
    NotAuthorizedError,
    UnknownActionError,
)
from features.authorization.composition.app_state import (
    set_authorization_container,
)
from features.authorization.composition.container import (
    AuthorizationContainer,
)


def attach_authorization_container(
    app: FastAPI, container: AuthorizationContainer
) -> None:
    """Publish the authorization port and container on ``app.state``."""
    app.state.authorization = container.port
    set_authorization_container(app, container)


def register_authorization_error_handlers(app: FastAPI) -> None:
    """Map authorization-domain exceptions to Problem Details responses.

    ``UnknownActionError`` is a programmer error (a route declared an
    action that no feature has registered on the registry) and SHALL
    surface as 500 so it shows up loudly in integration testing.
    ``NotAuthorizedError`` becomes 403; nothing in the current codebase
    raises it (denies use the boolean return), but a future caller
    might.
    """

    @app.exception_handler(UnknownActionError)
    async def _on_unknown_action(_request: Request, exc: UnknownActionError) -> Any:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "type": ProblemType.ABOUT_BLANK.value,
                "title": "Authorization configuration error",
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "detail": str(exc) or "Authorization configuration error",
            },
            media_type="application/problem+json",
        )

    @app.exception_handler(NotAuthorizedError)
    async def _on_not_authorized(_request: Request, exc: NotAuthorizedError) -> Any:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "type": ProblemType.AUTHZ_PERMISSION_DENIED.value,
                "title": "Permission denied",
                "status": status.HTTP_403_FORBIDDEN,
                "detail": str(exc) or "Permission denied",
            },
            media_type="application/problem+json",
        )
