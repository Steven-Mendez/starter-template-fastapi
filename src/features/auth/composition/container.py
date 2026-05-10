"""Composition root for the auth feature.

Builds and groups every collaborator (repository, use cases, rate
limiter, principal cache, authorization adapter) in a single container
so the rest of the application receives a single object instead of
dozens of individual dependencies. Tests construct their own container
with substitute components when they need to swap behaviour.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Union

from src.features.auth.adapters.outbound.authorization.sqlmodel import (
    SQLModelAuthorizationAdapter,
)
from src.features.auth.adapters.outbound.persistence.sqlmodel import (
    SQLModelAuthRepository,
)
from src.features.auth.application.authorization.ports import AuthorizationPort
from src.features.auth.application.cache import (
    InProcessPrincipalCache,
    PrincipalCachePort,
    RedisPrincipalCache,
)
from src.features.auth.application.crypto import PasswordService
from src.features.auth.application.jwt_tokens import AccessTokenService
from src.features.auth.application.rate_limit import (
    FixedWindowRateLimiter,
    RedisRateLimiter,
)
from src.features.auth.application.use_cases.admin.bootstrap_admin import (
    BootstrapSystemAdmin,
)
from src.features.auth.application.use_cases.admin.list_audit_events import (
    ListAuditEvents,
)
from src.features.auth.application.use_cases.admin.list_users import ListUsers
from src.features.auth.application.use_cases.auth.confirm_email_verification import (
    ConfirmEmailVerification,
)
from src.features.auth.application.use_cases.auth.confirm_password_reset import (
    ConfirmPasswordReset,
)
from src.features.auth.application.use_cases.auth.login_user import LoginUser
from src.features.auth.application.use_cases.auth.logout_user import (
    LogoutAllSessions,
    LogoutUser,
)
from src.features.auth.application.use_cases.auth.refresh_token import (
    RotateRefreshToken,
)
from src.features.auth.application.use_cases.auth.register_user import RegisterUser
from src.features.auth.application.use_cases.auth.request_email_verification import (
    RequestEmailVerification,
)
from src.features.auth.application.use_cases.auth.request_password_reset import (
    RequestPasswordReset,
)
from src.features.auth.application.use_cases.auth.resolve_principal import (
    ResolvePrincipalFromAccessToken,
)
from src.platform.config.settings import AppSettings

_logger = logging.getLogger(__name__)

RateLimiter = Union[FixedWindowRateLimiter, RedisRateLimiter]


@dataclass(slots=True)
class AuthContainer:
    """Bundle of every collaborator the auth feature needs at runtime."""

    settings: AppSettings
    repository: SQLModelAuthRepository
    rate_limiter: RateLimiter
    principal_cache: PrincipalCachePort
    authorization: AuthorizationPort
    shutdown: Callable[[], None]
    # Auth use cases
    register_user: RegisterUser
    login_user: LoginUser
    rotate_refresh_token: RotateRefreshToken
    logout_user: LogoutUser
    logout_all_sessions: LogoutAllSessions
    request_password_reset: RequestPasswordReset
    confirm_password_reset: ConfirmPasswordReset
    request_email_verification: RequestEmailVerification
    confirm_email_verification: ConfirmEmailVerification
    resolve_principal: ResolvePrincipalFromAccessToken
    # Admin use cases (gated by system:main checks at the HTTP layer)
    list_users: ListUsers
    list_audit_events: ListAuditEvents
    bootstrap_system_admin: BootstrapSystemAdmin


def build_auth_container(
    *,
    settings: AppSettings,
    repository: SQLModelAuthRepository | None = None,
) -> AuthContainer:
    """Wire all auth dependencies and return a ready-to-use container."""
    repo = repository or SQLModelAuthRepository(
        settings.postgresql_dsn,
        create_schema=False,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_recycle=settings.db_pool_recycle_seconds,
        pool_pre_ping=settings.db_pool_pre_ping,
    )
    password_service = PasswordService()

    if not settings.auth_jwt_secret_key:
        raise RuntimeError("APP_AUTH_JWT_SECRET_KEY is required at startup")

    token_service = AccessTokenService(settings)
    _warn_unused_oauth_settings(settings)
    _check_internal_token_exposure(settings)

    limiter: RateLimiter
    cache: PrincipalCachePort
    if settings.auth_redis_url:
        limiter = RedisRateLimiter.from_url(settings.auth_redis_url)
        cache = RedisPrincipalCache.from_url(
            settings.auth_redis_url,
            ttl=settings.auth_principal_cache_ttl_seconds,
        )
    else:
        limiter = FixedWindowRateLimiter()
        cache = InProcessPrincipalCache.create(
            ttl=settings.auth_principal_cache_ttl_seconds
        )
        if settings.auth_rate_limit_enabled:
            if settings.auth_require_distributed_rate_limit:
                raise RuntimeError(
                    "APP_AUTH_REQUIRE_DISTRIBUTED_RATE_LIMIT is true but "
                    "APP_AUTH_REDIS_URL is not configured"
                )
            _logger.error(
                "event=auth.rate_limit.degraded backend=in_memory "
                "distributed=false message=Using in-memory rate limiter; "
                "set APP_AUTH_REDIS_URL to enforce limits across replicas"
            )

    # Authorization adapter shares the auth repository's engine so cache
    # invalidation (via authz_version bumps on the users table) and tuple
    # writes hit the same database. Read paths do not need a parent resolver
    # because card/column checks are performed by use cases that wire a
    # session-scoped adapter with its own resolver via the kanban UoW.
    authorization = SQLModelAuthorizationAdapter(repo.engine)

    dummy_hash = password_service.hash_password("dummy-password")

    register_user = RegisterUser(
        _repository=repo,
        _password_service=password_service,
        _settings=settings,
    )

    def _shutdown() -> None:
        repo.close()
        limiter.close()
        cache.close()

    return AuthContainer(
        settings=settings,
        repository=repo,
        rate_limiter=limiter,
        principal_cache=cache,
        authorization=authorization,
        shutdown=_shutdown,
        register_user=register_user,
        login_user=LoginUser(
            _repository=repo,
            _password_service=password_service,
            _token_service=token_service,
            _settings=settings,
            _dummy_hash=dummy_hash,
        ),
        rotate_refresh_token=RotateRefreshToken(
            _repository=repo,
            _token_service=token_service,
            _settings=settings,
        ),
        logout_user=LogoutUser(_repository=repo, _cache=cache),
        logout_all_sessions=LogoutAllSessions(_repository=repo, _cache=cache),
        request_password_reset=RequestPasswordReset(
            _repository=repo,
            _settings=settings,
        ),
        confirm_password_reset=ConfirmPasswordReset(
            _repository=repo,
            _password_service=password_service,
            _cache=cache,
        ),
        request_email_verification=RequestEmailVerification(
            _repository=repo,
            _settings=settings,
        ),
        confirm_email_verification=ConfirmEmailVerification(
            _repository=repo,
            _cache=cache,
        ),
        resolve_principal=ResolvePrincipalFromAccessToken.create(
            repository=repo,
            token_service=token_service,
            settings=settings,
            cache=cache,
        ),
        list_users=ListUsers(_repository=repo),
        list_audit_events=ListAuditEvents(_repository=repo),
        bootstrap_system_admin=BootstrapSystemAdmin(
            _repository=repo,
            _register_user=register_user,
            _authorization=authorization,
        ),
    )


def _warn_unused_oauth_settings(settings: AppSettings) -> None:
    """Warn when OAuth config is present even though OAuth is not implemented."""
    if any(
        (
            settings.auth_oauth_enabled,
            settings.auth_oauth_google_client_id,
            settings.auth_oauth_google_client_secret,
            settings.auth_oauth_google_redirect_uri,
        )
    ):
        _logger.warning(
            "event=auth.oauth.unimplemented message=OAuth settings are configured "
            "but OAuth login is not implemented"
        )


def _check_internal_token_exposure(settings: AppSettings) -> None:
    """Reject ``auth_return_internal_tokens`` in production; otherwise log once."""
    if not settings.auth_return_internal_tokens:
        _logger.info(
            "event=auth.internal_tokens.suppressed "
            "message=Password-reset and email-verify tokens are kept out of API "
            "responses; configure a delivery provider to send them to users"
        )
        return
    if settings.environment == "production":
        raise RuntimeError(
            "APP_AUTH_RETURN_INTERNAL_TOKENS=true is forbidden in production"
        )
    _logger.warning(
        "event=auth.internal_tokens.exposed environment=%s "
        "message=Password-reset and email-verify tokens will be returned in "
        "API responses; only acceptable for local development and e2e tests",
        settings.environment,
    )
