"""HTTP routes for the public auth surface (register, login, refresh, etc.).

Each handler is a thin shell that:

* validates the request via Pydantic schemas,
* enforces rate limits and CSRF-style origin checks where relevant,
* delegates the actual flow to :class:`AuthService`,
* and translates domain errors into HTTP responses through
  :func:`raise_http_from_auth_error`.

Refresh tokens travel through an httpOnly cookie scoped to ``/auth`` so they
are never exposed to JavaScript or sent on regular API calls.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Cookie, HTTPException, Request, Response, status

from src.features.auth.adapters.inbound.http.dependencies import CurrentPrincipalDep
from src.features.auth.adapters.inbound.http.errors import raise_http_from_auth_error
from src.features.auth.adapters.inbound.http.schemas import (
    EmailVerifyRequest,
    InternalTokenResponse,
    LoginRequest,
    MessageResponse,
    PasswordForgotRequest,
    PasswordResetRequest,
    PrincipalPublic,
    RegisterRequest,
    TokenResponse,
    UserPublic,
)
from src.features.auth.application.errors import AuthError, RateLimitExceededError
from src.features.auth.application.types import IssuedTokens, Principal
from src.features.auth.composition.app_state import get_auth_container

REFRESH_COOKIE_NAME = "refresh_token"

auth_router = APIRouter(prefix="/auth", tags=["auth"])


def _client_ip(request: Request) -> str | None:
    """Return the client's IP address, or ``None`` if unavailable."""
    return request.client.host if request.client else None


def _user_agent(request: Request) -> str | None:
    """Return the client's User-Agent header, or ``None`` if not sent."""
    return request.headers.get("user-agent")


def _principal_response(principal: Principal) -> PrincipalPublic:
    """Convert a domain ``Principal`` to the public-facing response schema.

    Roles and permissions are sorted for deterministic API output.
    """
    return PrincipalPublic(
        id=principal.user_id,
        email=principal.email,
        is_active=principal.is_active,
        is_verified=principal.is_verified,
        roles=sorted(principal.roles),
        permissions=sorted(principal.permissions),
    )


def _set_refresh_cookie(
    response: Response, request: Request, tokens: IssuedTokens
) -> None:
    """Attach the refresh token as a hardened cookie on the outgoing response.

    The cookie is restricted to the ``/auth`` path and marked ``httpOnly``
    so JavaScript on the host page cannot read it even if XSS is achieved.
    Lifetime mirrors the configured refresh-token expiry.
    """
    settings = get_auth_container(request).settings
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=tokens.refresh_token,
        max_age=settings.auth_refresh_token_expire_days * 24 * 60 * 60,
        # Scoping to /auth keeps the cookie out of regular API calls, so it
        # is only ever sent to refresh/logout endpoints.
        path="/auth",
        secure=settings.auth_cookie_secure,
        httponly=True,
        samesite=settings.auth_cookie_samesite,
    )


def _clear_refresh_cookie(response: Response, request: Request) -> None:
    """Instruct the browser to delete the refresh-token cookie."""
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        path="/auth",
    )


def _enforce_cookie_origin(request: Request) -> None:
    """Reject cross-origin requests that would carry the refresh-token cookie.

    Browsers attach cookies automatically on cross-site requests, which
    makes cookie-authenticated endpoints vulnerable to CSRF. Validating
    ``Origin`` against the configured allow-list closes that gap before
    any business logic runs.

    Raises:
        HTTPException 403: If ``Origin`` is set but not in ``cors_origins``.
    """
    origin = request.headers.get("origin")
    if origin is None:
        return
    settings = get_auth_container(request).settings
    if settings.cors_origins == ["*"] or "*" in settings.cors_origins:
        # Wildcard CORS is only permitted in development/test environments.
        # Production settings validation rejects cors_origins=["*"], so this
        # branch is unreachable in production.
        return
    if origin not in settings.cors_origins:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Untrusted origin",
        )


def _check_rate_limit(request: Request, key: str) -> None:
    """Apply the configured per-endpoint rate limit, raising 429 on excess.

    The composite key (path + IP + identifier) ensures limits are scoped per
    endpoint and per client, so one abusive client cannot block other users
    from using the same endpoint.

    Args:
        request: Incoming request, used to resolve path and client IP.
        key: Caller-supplied identifier (e.g. the email being attempted).
    """
    container = get_auth_container(request)
    if not container.settings.auth_rate_limit_enabled:
        return
    try:
        container.rate_limiter.check(f"{request.url.path}:{_client_ip(request)}:{key}")
    except RateLimitExceededError as exc:
        raise_http_from_auth_error(exc)


@auth_router.post(
    "/register",
    response_model=UserPublic,
    status_code=status.HTTP_201_CREATED,
)
def register(body: RegisterRequest, request: Request) -> UserPublic:
    """Register a new user account and return the created user's public data."""
    try:
        user = get_auth_container(request).auth_service.register(
            email=body.email,
            password=body.password,
            ip_address=_client_ip(request),
            user_agent=_user_agent(request),
        )
        return UserPublic.model_validate(user)
    except AuthError as exc:
        raise_http_from_auth_error(exc)


@auth_router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, request: Request, response: Response) -> TokenResponse:
    """Authenticate credentials and return a token pair.

    The refresh token is set as an httpOnly cookie; the access token is in the
    response body. Rate-limited per email per IP to slow down brute-force attacks.
    """
    _check_rate_limit(request, body.email)
    try:
        tokens, principal = get_auth_container(request).auth_service.login(
            email=body.email,
            password=body.password,
            ip_address=_client_ip(request),
            user_agent=_user_agent(request),
        )
        _set_refresh_cookie(response, request, tokens)
        return TokenResponse(
            access_token=tokens.access_token,
            token_type=tokens.token_type,
            expires_in=tokens.expires_in,
            user=_principal_response(principal),
        )
    except AuthError as exc:
        raise_http_from_auth_error(exc)


@auth_router.post("/refresh", response_model=TokenResponse)
def refresh(
    request: Request,
    response: Response,
    refresh_token: Annotated[str | None, Cookie(alias=REFRESH_COOKIE_NAME)] = None,
) -> TokenResponse:
    """Rotate the refresh token and issue a new token pair.

    Origin is validated to prevent CSRF; the refresh token is read from the
    httpOnly cookie and must not be sent in the request body.
    """
    _enforce_cookie_origin(request)
    try:
        tokens, principal = get_auth_container(request).auth_service.refresh(
            refresh_token=refresh_token,
            ip_address=_client_ip(request),
            user_agent=_user_agent(request),
        )
        _set_refresh_cookie(response, request, tokens)
        return TokenResponse(
            access_token=tokens.access_token,
            token_type=tokens.token_type,
            expires_in=tokens.expires_in,
            user=_principal_response(principal),
        )
    except AuthError as exc:
        raise_http_from_auth_error(exc)


@auth_router.post("/logout", response_model=MessageResponse)
def logout(
    request: Request,
    response: Response,
    refresh_token: Annotated[str | None, Cookie(alias=REFRESH_COOKIE_NAME)] = None,
) -> MessageResponse:
    """Revoke the current session and clear the refresh-token cookie."""
    _enforce_cookie_origin(request)
    get_auth_container(request).auth_service.logout(refresh_token)
    _clear_refresh_cookie(response, request)
    return MessageResponse(message="Logged out")


@auth_router.post("/logout-all", response_model=MessageResponse)
def logout_all(
    principal: CurrentPrincipalDep,
    request: Request,
    response: Response,
) -> MessageResponse:
    """Revoke all active sessions for the authenticated user across all devices."""
    try:
        get_auth_container(request).auth_service.logout_all(
            user_id=principal.user_id,
            ip_address=_client_ip(request),
            user_agent=_user_agent(request),
        )
        _clear_refresh_cookie(response, request)
        return MessageResponse(message="All sessions revoked")
    except AuthError as exc:
        raise_http_from_auth_error(exc)


@auth_router.get("/me", response_model=PrincipalPublic)
def me(principal: CurrentPrincipalDep) -> PrincipalPublic:
    """Return the authenticated user's identity, roles, and permissions."""
    return _principal_response(principal)


@auth_router.post("/password/forgot", response_model=InternalTokenResponse)
def forgot_password(
    body: PasswordForgotRequest, request: Request
) -> InternalTokenResponse:
    """Initiate a password-reset flow for the given email.

    Always responds with 200 and the same message regardless of whether the
    account exists, to prevent user enumeration via this endpoint.
    Rate-limited per email per IP to slow down abuse.
    """
    _check_rate_limit(request, body.email)
    try:
        result = get_auth_container(request).auth_service.request_password_reset(
            email=body.email,
            ip_address=_client_ip(request),
        )
        # The vague message is intentional: always responding with 200 and the
        # same text prevents user enumeration via the password-reset endpoint.
        return InternalTokenResponse(
            message="If the account exists, a reset token has been created",
            dev_token=result.token,
            expires_at=result.expires_at,
        )
    except AuthError as exc:
        raise_http_from_auth_error(exc)


@auth_router.post("/password/reset", response_model=MessageResponse)
def reset_password(body: PasswordResetRequest, request: Request) -> MessageResponse:
    """Apply a new password using a single-use reset token.

    Rate-limited on the first 16 characters of the token to prevent
    rapid-fire brute-force without exposing the full token in the rate-limit key.
    All existing sessions are revoked after a successful reset.
    """
    _check_rate_limit(request, body.token[:16])
    try:
        get_auth_container(request).auth_service.reset_password(
            token=body.token,
            new_password=body.new_password,
        )
        return MessageResponse(message="Password reset complete")
    except AuthError as exc:
        raise_http_from_auth_error(exc)


@auth_router.post("/email/verify/request", response_model=InternalTokenResponse)
def request_email_verify(
    principal: CurrentPrincipalDep, request: Request
) -> InternalTokenResponse:
    """Issue an email-verification token for the authenticated user."""
    try:
        result = get_auth_container(request).auth_service.request_email_verification(
            user_id=principal.user_id,
            ip_address=_client_ip(request),
        )
        return InternalTokenResponse(
            message="Email verification token created",
            dev_token=result.token,
            expires_at=result.expires_at,
        )
    except AuthError as exc:
        raise_http_from_auth_error(exc)


@auth_router.post("/email/verify", response_model=MessageResponse)
def verify_email(body: EmailVerifyRequest, request: Request) -> MessageResponse:
    """Consume a single-use verification token and mark the account as verified."""
    try:
        get_auth_container(request).auth_service.verify_email(token=body.token)
        return MessageResponse(message="Email verified")
    except AuthError as exc:
        raise_http_from_auth_error(exc)
