"""HTTP routes for the public auth surface (register, login, refresh, etc.).

Each handler is a thin shell that:

* validates the request via Pydantic schemas,
* enforces rate limits and CSRF-style origin checks where relevant,
* delegates the actual flow to the relevant use-case instance,
* and translates domain errors into HTTP responses through
  :func:`raise_http_from_auth_error`.

Refresh tokens travel through an httpOnly cookie scoped to ``/auth`` so they
are never exposed to JavaScript or sent on regular API calls.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Annotated
from urllib.parse import urlsplit

from fastapi import APIRouter, Cookie, HTTPException, Request, Response, status

from app_platform.api.operation_ids import feature_operation_id
from app_platform.api.responses import AUTH_RESPONSES
from app_platform.observability.tracing import traced
from app_platform.shared.principal import Principal
from app_platform.shared.result import Err, Ok
from features.authentication.adapters.inbound.http.cookies import (
    REFRESH_COOKIE_NAME,
    clear_refresh_cookie,
)
from features.authentication.adapters.inbound.http.dependencies import (
    CurrentPrincipalDep,
)
from features.authentication.adapters.inbound.http.errors import (
    raise_http_from_auth_error,
)
from features.authentication.adapters.inbound.http.schemas import (
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
from features.authentication.application.errors import RateLimitExceededError
from features.authentication.application.types import IssuedTokens
from features.authentication.composition.app_state import get_auth_container

auth_router = APIRouter(
    prefix="/auth",
    tags=["auth"],
    generate_unique_id_function=feature_operation_id,
)

_rate_limit_logger = logging.getLogger("auth.rate_limit")


def _client_ip(request: Request) -> str | None:
    """Return the client's IP address, or ``None`` if unavailable.

    ``request.client.host`` is rewritten upstream by
    ``uvicorn.middleware.proxy_headers.ProxyHeadersMiddleware`` when
    the request originated from a trusted proxy in
    ``APP_TRUSTED_PROXY_IPS`` — so this helper returns the real client
    IP behind a configured load balancer, and the unmodified socket
    peer otherwise.
    """
    return request.client.host if request.client else None


def _account_key(action: str, identifier: str | None) -> str:
    """Build a per-account rate-limit key.

    ``action`` is one of ``"login"``, ``"register"``, ``"reset"``,
    ``"verify"``; ``identifier`` is the email pre-resolution (or the
    user id once resolved). Returns a key shape that does NOT include
    the request path or client IP so the per-account budget is
    enforced regardless of IP diversity — that is the entire point of
    the per-account limiter.
    """
    return f"per_account:{action}:{identifier or 'unknown'}"


def _user_agent(request: Request) -> str | None:
    """Return the client's User-Agent header, or ``None`` if not sent."""
    return request.headers.get("user-agent")


def _principal_response(principal: Principal) -> PrincipalPublic:
    """Convert a domain ``Principal`` to the public-facing response schema."""
    return PrincipalPublic(
        id=principal.user_id,
        email=principal.email,
        is_active=principal.is_active,
        is_verified=principal.is_verified,
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


def _referer_origin(referer: str) -> str | None:
    """Return the ``scheme://host[:port]`` origin of a ``Referer`` URL.

    Returns ``None`` for malformed or scheme-less values so callers can
    treat them the same as a missing header.
    """
    try:
        parts = urlsplit(referer)
    except ValueError:
        return None
    if not parts.scheme or not parts.hostname:
        return None
    host = parts.hostname
    if parts.port is not None:
        host = f"{host}:{parts.port}"
    return f"{parts.scheme}://{host}"


def _enforce_cookie_origin(request: Request) -> None:
    """Reject cross-origin requests that would carry the refresh-token cookie.

    Browsers attach cookies automatically on cross-site requests, which
    makes cookie-authenticated endpoints vulnerable to CSRF. The check
    requires *either* a trusted ``Origin`` header *or* a trusted
    ``Referer`` origin; if both are missing on a request that carries
    the refresh cookie, the request is refused with 403.

    Raises:
        HTTPException 403: If ``Origin`` is set but not in
            ``cors_origins``; if ``Referer`` is set but its origin is
            not in ``cors_origins`` and ``Origin`` is absent; or if both
            headers are absent and the refresh cookie is present on the
            request.
    """
    settings = get_auth_container(request).settings
    wildcard = settings.cors_origins == ["*"] or "*" in settings.cors_origins
    trusted = set(settings.cors_origins)

    origin = request.headers.get("origin")
    if origin is not None:
        if wildcard:
            # Wildcard CORS is only permitted in development/test
            # environments. Production settings validation rejects
            # cors_origins=["*"], so this branch is unreachable in
            # production.
            return
        if origin not in trusted:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Untrusted origin",
            )
        return

    # ``Origin`` is absent. Fall back to ``Referer`` so legitimate
    # navigations and form-style POSTs (which some browsers send without
    # ``Origin`` on same-site requests) are not blocked, while still
    # closing the cross-site channel.
    referer = request.headers.get("referer")
    if referer is not None:
        referer_origin = _referer_origin(referer)
        if referer_origin is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Untrusted origin",
            )
        if wildcard:
            return
        if referer_origin not in trusted:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Untrusted origin",
            )
        return

    # Both headers are absent. If the request carries the refresh cookie
    # there is no signal of provenance to validate — refuse. If the
    # refresh cookie is also absent the request cannot leverage cookie-
    # authenticated state, so it stays a no-op for backwards compat.
    if REFRESH_COOKIE_NAME in request.cookies:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Untrusted origin",
        )


@traced(
    "auth.rate_limit",
    attrs=lambda request, key: {
        "rate_limit.key_hash": hashlib.sha256(
            f"{request.url.path}:{key}".encode()
        ).hexdigest()[:16],
    },
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
        _rate_limit_logger.warning(
            "event=auth.rate_limit.tripped scope=per_ip path=%s key_hash=%s",
            request.url.path,
            hashlib.sha256(f"{request.url.path}:{key}".encode()).hexdigest()[:16],
        )
        raise_http_from_auth_error(exc)


def _check_per_account_rate_limit(
    request: Request, action: str, identifier: str | None
) -> None:
    """Apply the per-account lockout limiter for ``action`` on ``identifier``.

    AND-composed with :func:`_check_rate_limit` in the route handlers:
    the per-(ip, email) limiter runs first (cheap, blocks single-IP
    bursts), then this per-account limiter runs (covers botnets of
    distinct IPs targeting one account). Both must pass for the
    request to proceed.

    On trip, a distinct log event tagged ``per_account`` is emitted so
    dashboards can separate account-targeted attacks (botnet
    credential-stuffing) from per-IP bursts.

    Args:
        request: Incoming request — used to resolve the auth container.
        action: One of ``"login"``, ``"reset"``, ``"verify"`` — picks
            which limiter to use.
        identifier: Email (pre-resolution) or user id; falls back to
            ``"unknown"`` when missing.
    """
    container = get_auth_container(request)
    if not container.settings.auth_rate_limit_enabled:
        return
    if action == "login":
        limiter = container.per_account_login_limiter
    elif action == "reset":
        limiter = container.per_account_reset_limiter
    elif action == "verify":
        limiter = container.per_account_verify_limiter
    else:
        raise ValueError(
            f"unknown per-account rate-limit action: {action!r}; "
            "expected one of 'login', 'reset', 'verify'"
        )
    key = _account_key(action, identifier)
    try:
        limiter.check(key)
    except RateLimitExceededError as exc:
        _rate_limit_logger.warning(
            "event=auth.rate_limit.tripped scope=per_account action=%s "
            "identifier_hash=%s",
            action,
            hashlib.sha256((identifier or "unknown").encode()).hexdigest()[:16],
        )
        raise_http_from_auth_error(exc)


@auth_router.post(
    "/register",
    response_model=UserPublic,
    status_code=status.HTTP_201_CREATED,
    responses=AUTH_RESPONSES,
)
def register(body: RegisterRequest, request: Request) -> UserPublic:
    """Register a new user account and return the created user's public data."""
    # Registration hashes passwords, so limit by IP instead of email to avoid
    # trivial bypass with random addresses.
    _check_rate_limit(request, "registration")
    # Per-account budget: a botnet that rotates IPs to register under a
    # single targeted email still trips this limiter. Reuses the
    # ``login`` per-account knobs because the budget is conceptually
    # "attempts to acquire an account for this email".
    _check_per_account_rate_limit(request, "login", body.email)
    result = get_auth_container(request).register_user.execute(
        email=body.email,
        password=body.password,
        ip_address=_client_ip(request),
        user_agent=_user_agent(request),
    )
    match result:
        case Ok(value=user):
            return UserPublic.model_validate(user)
        case Err(error=exc):
            raise_http_from_auth_error(exc)
    return None


@auth_router.post("/login", response_model=TokenResponse, responses=AUTH_RESPONSES)
def login(body: LoginRequest, request: Request, response: Response) -> TokenResponse:
    """Authenticate credentials and return a token pair.

    The refresh token is set as an httpOnly cookie; the access token is in the
    response body. Rate-limited per email per IP to slow down brute-force attacks.
    """
    _check_rate_limit(request, body.email)
    _check_per_account_rate_limit(request, "login", body.email)
    result = get_auth_container(request).login_user.execute(
        email=body.email,
        password=body.password,
        ip_address=_client_ip(request),
        user_agent=_user_agent(request),
    )
    match result:
        case Ok(value=(tokens, principal)):
            _set_refresh_cookie(response, request, tokens)
            return TokenResponse(
                access_token=tokens.access_token,
                token_type=tokens.token_type,
                expires_in=tokens.expires_in,
                user=_principal_response(principal),
            )
        case Err(error=exc):
            raise_http_from_auth_error(exc)
    return None


@auth_router.post("/refresh", response_model=TokenResponse, responses=AUTH_RESPONSES)
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
    result = get_auth_container(request).rotate_refresh_token.execute(
        refresh_token=refresh_token,
        ip_address=_client_ip(request),
        user_agent=_user_agent(request),
    )
    match result:
        case Ok(value=(tokens, principal)):
            _set_refresh_cookie(response, request, tokens)
            return TokenResponse(
                access_token=tokens.access_token,
                token_type=tokens.token_type,
                expires_in=tokens.expires_in,
                user=_principal_response(principal),
            )
        case Err(error=exc):
            raise_http_from_auth_error(exc)
    return None


@auth_router.post("/logout", response_model=MessageResponse, responses=AUTH_RESPONSES)
def logout(
    request: Request,
    response: Response,
    refresh_token: Annotated[str | None, Cookie(alias=REFRESH_COOKIE_NAME)] = None,
) -> MessageResponse:
    """Revoke the current session and clear the refresh-token cookie."""
    _enforce_cookie_origin(request)
    get_auth_container(request).logout_user.execute(refresh_token)
    clear_refresh_cookie(response, request)
    return MessageResponse(message="Logged out")


@auth_router.post(
    "/logout-all", response_model=MessageResponse, responses=AUTH_RESPONSES
)
def logout_all(
    principal: CurrentPrincipalDep,
    request: Request,
    response: Response,
) -> MessageResponse:
    """Revoke all active sessions for the authenticated user across all devices."""
    result = get_auth_container(request).logout_all_sessions.execute(
        user_id=principal.user_id,
        ip_address=_client_ip(request),
        user_agent=_user_agent(request),
    )
    match result:
        case Ok():
            clear_refresh_cookie(response, request)
            return MessageResponse(message="All sessions revoked")
        case Err(error=exc):
            raise_http_from_auth_error(exc)
    return None


@auth_router.get("/me", response_model=PrincipalPublic, responses=AUTH_RESPONSES)
def me(principal: CurrentPrincipalDep) -> PrincipalPublic:
    """Return the authenticated user's identity, roles, and permissions."""
    return _principal_response(principal)


@auth_router.post(
    "/password/forgot",
    response_model=InternalTokenResponse,
    status_code=202,
    responses=AUTH_RESPONSES,
)
def forgot_password(
    body: PasswordForgotRequest, request: Request
) -> InternalTokenResponse:
    """Initiate a password-reset flow for the given email.

    Always responds with 200 and the same message regardless of whether the
    account exists, to prevent user enumeration via this endpoint.
    Rate-limited per email per IP to slow down abuse.
    """
    _check_rate_limit(request, body.email)
    _check_per_account_rate_limit(request, "reset", body.email)
    result = get_auth_container(request).request_password_reset.execute(
        email=body.email,
        ip_address=_client_ip(request),
    )
    match result:
        case Ok(value=token_result):
            # The vague message is intentional: always responding with 200 and the
            # same text prevents user enumeration via the password-reset endpoint.
            return InternalTokenResponse(
                message="If the account exists, a reset token has been created",
                dev_token=token_result.token,
                expires_at=token_result.expires_at,
            )
        case Err(error=exc):
            raise_http_from_auth_error(exc)
    return None


@auth_router.post(
    "/password/reset", response_model=MessageResponse, responses=AUTH_RESPONSES
)
def reset_password(body: PasswordResetRequest, request: Request) -> MessageResponse:
    """Apply a new password using a single-use reset token.

    Rate-limited on a SHA-256 prefix of the token so the rate-limit key
    has full token entropy without storing the token itself in memory or
    Redis. All existing sessions are revoked after a successful reset.
    """
    token_key = hashlib.sha256(body.token.encode("utf-8")).hexdigest()[:32]
    _check_rate_limit(request, token_key)
    result = get_auth_container(request).confirm_password_reset.execute(
        token=body.token,
        new_password=body.new_password,
    )
    match result:
        case Ok():
            return MessageResponse(message="Password reset complete")
        case Err(error=exc):
            raise_http_from_auth_error(exc)
    return None


@auth_router.post(
    "/email/verify/request",
    response_model=InternalTokenResponse,
    status_code=202,
    responses=AUTH_RESPONSES,
)
def request_email_verify(
    principal: CurrentPrincipalDep, request: Request
) -> InternalTokenResponse:
    """Issue an email-verification token for the authenticated user."""
    _check_rate_limit(request, str(principal.user_id))
    _check_per_account_rate_limit(request, "verify", str(principal.user_id))
    result = get_auth_container(request).request_email_verification.execute(
        user_id=principal.user_id,
        ip_address=_client_ip(request),
    )
    match result:
        case Ok(value=token_result):
            return InternalTokenResponse(
                message="Email verification token created",
                dev_token=token_result.token,
                expires_at=token_result.expires_at,
            )
        case Err(error=exc):
            raise_http_from_auth_error(exc)
    return None


@auth_router.post(
    "/email/verify", response_model=MessageResponse, responses=AUTH_RESPONSES
)
def verify_email(body: EmailVerifyRequest, request: Request) -> MessageResponse:
    """Consume a single-use verification token and mark the account as verified."""
    result = get_auth_container(request).confirm_email_verification.execute(
        token=body.token
    )
    match result:
        case Ok():
            return MessageResponse(message="Email verified")
        case Err(error=exc):
            raise_http_from_auth_error(exc)
    return None
