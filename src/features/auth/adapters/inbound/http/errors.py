"""Mapping from domain auth errors to HTTPException responses.

Centralising the translation here keeps individual routers free of HTTP
status knowledge and makes the full mapping easy to audit or change.
"""

from __future__ import annotations

from typing import NoReturn

from fastapi import HTTPException, status

from src.features.auth.application.errors import (
    AuthError,
    ConfigurationError,
    ConflictError,
    DuplicateEmailError,
    EmailNotVerifiedError,
    InactiveUserError,
    InvalidCredentialsError,
    InvalidTokenError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitExceededError,
    StaleTokenError,
    TokenAlreadyUsedError,
)
from src.platform.api.error_handlers_app_exception import ApplicationHTTPException

EXPLICIT_AUTH_ERROR_TYPES: tuple[type[AuthError], ...] = (
    ConfigurationError,
    ConflictError,
    DuplicateEmailError,
    EmailNotVerifiedError,
    InactiveUserError,
    InvalidCredentialsError,
    InvalidTokenError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitExceededError,
    StaleTokenError,
    TokenAlreadyUsedError,
)


def raise_http_from_auth_error(exc: AuthError) -> NoReturn:
    """Translate an :class:`AuthError` into the appropriate HTTPException and raise it.

    The mapping intentionally collapses several domain failures onto the
    same HTTP status (for example, ``InvalidCredentialsError`` and
    ``InvalidTokenError`` both produce 401) so the API does not leak
    information that could help an attacker enumerate accounts or token
    states.

    Args:
        exc: The domain error caught by the router.

    Raises:
        HTTPException: A status-appropriate response for the given error.
            Unknown subclasses fall back to a generic 400.
    """
    if isinstance(exc, DuplicateEmailError):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        ) from exc
    if isinstance(exc, InvalidCredentialsError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    if isinstance(exc, StaleTokenError):
        # Distinguish stale tokens from structurally invalid ones so clients
        # know to re-authenticate (permission set changed) rather than assume
        # the token is corrupt or expired.
        raise ApplicationHTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is stale — re-authentication required",
            code="stale_token",
            type_uri="about:blank",
        ) from exc
    if isinstance(exc, InvalidTokenError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    if isinstance(exc, InactiveUserError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account inactive",
        ) from exc
    if isinstance(exc, EmailNotVerifiedError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified",
        ) from exc
    if isinstance(exc, PermissionDeniedError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        ) from exc
    if isinstance(exc, NotFoundError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc) or "Not found",
        ) from exc
    if isinstance(exc, TokenAlreadyUsedError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token already used",
        ) from exc
    if isinstance(exc, ConflictError):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc) or "Conflict",
        ) from exc
    if isinstance(exc, RateLimitExceededError):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
        ) from exc
    if isinstance(exc, ConfigurationError):
        # 503 rather than 500 signals that the service is temporarily
        # unavailable due to missing configuration, not a bug in request
        # handling, so load balancers can route around it.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured",
        ) from exc
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
    ) from exc
