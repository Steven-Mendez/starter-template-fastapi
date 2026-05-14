"""Mapping from domain auth errors to HTTPException responses.

Centralising the translation here keeps individual routers free of HTTP
status knowledge and makes the full mapping easy to audit or change.
"""

from __future__ import annotations

from typing import NoReturn

from fastapi import status

from app_platform.api.error_handlers_app_exception import ApplicationHTTPException
from app_platform.api.problem_types import ProblemType
from features.authentication.application.errors import (
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
    states. The ``type_uri`` carried on each :class:`ApplicationHTTPException`
    distinguishes them for clients via the RFC 9457 ``type`` field.

    Args:
        exc: The domain error caught by the router.

    Raises:
        ApplicationHTTPException: A status-appropriate Problem Details
            response for the given error. Unknown subclasses fall back
            to a generic 400 with ``ProblemType.ABOUT_BLANK``.
    """
    if isinstance(exc, DuplicateEmailError):
        raise ApplicationHTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
            code="duplicate_email",
            type_uri=ProblemType.GENERIC_CONFLICT,
        ) from exc
    if isinstance(exc, InvalidCredentialsError):
        raise ApplicationHTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            code="invalid_credentials",
            type_uri=ProblemType.AUTH_INVALID_CREDENTIALS,
        ) from exc
    if isinstance(exc, StaleTokenError):
        # Distinguish stale tokens from structurally invalid ones so clients
        # know to re-authenticate (permission set changed) rather than assume
        # the token is corrupt or expired.
        raise ApplicationHTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is stale — re-authentication required",
            code="stale_token",
            type_uri=ProblemType.AUTH_TOKEN_STALE,
        ) from exc
    if isinstance(exc, InvalidTokenError):
        raise ApplicationHTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            code="invalid_token",
            type_uri=ProblemType.AUTH_TOKEN_INVALID,
        ) from exc
    if isinstance(exc, InactiveUserError):
        raise ApplicationHTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account inactive",
            code="inactive_user",
            type_uri=ProblemType.AUTHZ_PERMISSION_DENIED,
        ) from exc
    if isinstance(exc, EmailNotVerifiedError):
        raise ApplicationHTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified",
            code="email_not_verified",
            type_uri=ProblemType.AUTH_EMAIL_NOT_VERIFIED,
        ) from exc
    if isinstance(exc, PermissionDeniedError):
        raise ApplicationHTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
            code="permission_denied",
            type_uri=ProblemType.AUTHZ_PERMISSION_DENIED,
        ) from exc
    if isinstance(exc, NotFoundError):
        raise ApplicationHTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc) or "Not found",
            code="not_found",
            type_uri=ProblemType.GENERIC_NOT_FOUND,
        ) from exc
    if isinstance(exc, TokenAlreadyUsedError):
        raise ApplicationHTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token already used",
            code="token_already_used",
            type_uri=ProblemType.AUTH_TOKEN_INVALID,
        ) from exc
    if isinstance(exc, ConflictError):
        raise ApplicationHTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc) or "Conflict",
            code="conflict",
            type_uri=ProblemType.GENERIC_CONFLICT,
        ) from exc
    if isinstance(exc, RateLimitExceededError):
        raise ApplicationHTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            code="rate_limit_exceeded",
            type_uri=ProblemType.AUTH_RATE_LIMITED,
        ) from exc
    if isinstance(exc, ConfigurationError):
        # 503 rather than 500 signals that the service is temporarily
        # unavailable due to missing configuration, not a bug in request
        # handling, so load balancers can route around it.
        raise ApplicationHTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured",
            code="auth_not_configured",
            type_uri=ProblemType.ABOUT_BLANK,
        ) from exc
    raise ApplicationHTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=str(exc),
        code="auth_error",
        type_uri=ProblemType.ABOUT_BLANK,
    ) from exc
