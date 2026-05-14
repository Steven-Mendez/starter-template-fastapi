"""Mapping from domain users-feature errors to HTTP Problem Details responses.

Centralising the translation here keeps individual route handlers free of
HTTP status knowledge and makes the full mapping easy to audit. Mirrors
``features.authentication.adapters.inbound.http.errors``.
"""

from __future__ import annotations

from typing import NoReturn

from fastapi import status

from app_platform.api.error_handlers_app_exception import ApplicationHTTPException
from app_platform.api.problem_types import ProblemType
from features.users.application.errors import (
    UserAlreadyExistsError,
    UserError,
    UserNotFoundError,
)


def raise_http_from_user_error(exc: UserError) -> NoReturn:
    """Translate a :class:`UserError` into a Problem Details HTTPException and raise.

    Args:
        exc: The domain error caught by the router.

    Raises:
        ApplicationHTTPException: A status-appropriate Problem Details
            response carrying the matching :class:`ProblemType` URN.
            Unknown subclasses fall back to a generic 400 with
            ``ProblemType.ABOUT_BLANK``.
    """
    if isinstance(exc, UserNotFoundError):
        raise ApplicationHTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
            code="user_not_found",
            type_uri=ProblemType.GENERIC_NOT_FOUND,
        ) from exc
    if isinstance(exc, UserAlreadyExistsError):
        raise ApplicationHTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already in use",
            code="user_already_exists",
            type_uri=ProblemType.GENERIC_CONFLICT,
        ) from exc
    raise ApplicationHTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=str(exc),
        code="user_error",
        type_uri=ProblemType.ABOUT_BLANK,
    ) from exc
