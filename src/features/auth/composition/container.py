"""Composition root for the auth feature.

Builds and groups every collaborator (repository, use cases, rate limiter)
in a single container so the rest of the application receives a single
object instead of dozens of individual dependencies. Tests construct
their own container with substitute components when they need to swap
behaviour.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Union

from src.features.auth.adapters.outbound.persistence.sqlmodel import (
    SQLModelAuthRepository,
)
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
from src.features.auth.application.use_cases.rbac.assign_role_permission import (
    AssignRolePermission,
)
from src.features.auth.application.use_cases.rbac.assign_user_role import AssignUserRole
from src.features.auth.application.use_cases.rbac.bootstrap_super_admin import (
    BootstrapSuperAdmin,
)
from src.features.auth.application.use_cases.rbac.create_permission import (
    CreatePermission,
)
from src.features.auth.application.use_cases.rbac.create_role import CreateRole
from src.features.auth.application.use_cases.rbac.list_audit_events import (
    ListAuditEvents,
)
from src.features.auth.application.use_cases.rbac.list_permissions import (
    ListPermissions,
)
from src.features.auth.application.use_cases.rbac.list_roles import ListRoles
from src.features.auth.application.use_cases.rbac.list_users import ListUsers
from src.features.auth.application.use_cases.rbac.remove_role_permission import (
    RemoveRolePermission,
)
from src.features.auth.application.use_cases.rbac.remove_user_role import RemoveUserRole
from src.features.auth.application.use_cases.rbac.seed_initial_data import (
    SeedInitialData,
)
from src.features.auth.application.use_cases.rbac.update_role import UpdateRole
from src.platform.config.settings import AppSettings

_logger = logging.getLogger(__name__)

RateLimiter = Union[FixedWindowRateLimiter, RedisRateLimiter]


@dataclass(slots=True)
class AuthContainer:
    """Bundle of every collaborator the auth feature needs at runtime.

    Attributes:
        settings: Effective application settings.
        repository: Persistence adapter shared across use cases.
        rate_limiter: Either the in-process or the Redis-backed limiter.
        principal_cache: Cache for resolved principals.
        shutdown: Callback invoked during application shutdown to release
            external resources (DB pool, Redis connection, ...).
        register_user: Use case for new user registration.
        login_user: Use case for credential authentication.
        rotate_refresh_token: Use case for refresh-token rotation.
        logout_user: Use case for single-session logout.
        logout_all_sessions: Use case for revoking all active sessions.
        request_password_reset: Use case for initiating a password reset.
        confirm_password_reset: Use case for applying a reset token.
        request_email_verification: Use case for requesting email verification.
        confirm_email_verification: Use case for consuming a verify token.
        resolve_principal: Use case for resolving a JWT to a Principal.
        list_roles / list_users / ...: RBAC management use cases.
        seed_initial_data: Use case that seeds default roles and permissions.
        bootstrap_super_admin: Use case for one-time super-admin creation.
    """

    settings: AppSettings
    repository: SQLModelAuthRepository
    rate_limiter: RateLimiter
    principal_cache: PrincipalCachePort
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
    # RBAC use cases
    list_roles: ListRoles
    list_users: ListUsers
    create_role: CreateRole
    update_role: UpdateRole
    list_permissions: ListPermissions
    create_permission: CreatePermission
    assign_role_permission: AssignRolePermission
    remove_role_permission: RemoveRolePermission
    assign_user_role: AssignUserRole
    remove_user_role: RemoveUserRole
    list_audit_events: ListAuditEvents
    seed_initial_data: SeedInitialData
    bootstrap_super_admin: BootstrapSuperAdmin


def build_auth_container(
    *,
    settings: AppSettings,
    repository: SQLModelAuthRepository | None = None,
) -> AuthContainer:
    """Wire all auth dependencies and return a ready-to-use container.

    Selects the rate limiter based on ``settings.auth_redis_url``:
    ``RedisRateLimiter`` when a URL is provided, ``FixedWindowRateLimiter``
    otherwise. The Redis limiter pings the server at construction, so an
    invalid URL fails loudly here rather than on the first request.

    Args:
        settings: Application settings, typically loaded from the environment.
        repository: An optional pre-built repository. When ``None``, a new
            ``SQLModelAuthRepository`` connected to ``settings.postgresql_dsn``
            is created automatically. Pass an explicit repository in tests to
            inject a SQLite in-memory engine.

    Returns:
        A fully initialised ``AuthContainer``.
    """
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

    dummy_hash = password_service.hash_password("dummy-password")

    register_user = RegisterUser(
        _repository=repo,
        _password_service=password_service,
        _settings=settings,
    )
    seed = SeedInitialData(_repository=repo)

    def _shutdown() -> None:
        repo.close()
        limiter.close()
        cache.close()

    return AuthContainer(
        settings=settings,
        repository=repo,
        rate_limiter=limiter,
        principal_cache=cache,
        shutdown=_shutdown,
        # Auth use cases
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
        # RBAC use cases
        list_roles=ListRoles(_repository=repo),
        list_users=ListUsers(_repository=repo),
        create_role=CreateRole(_repository=repo),
        update_role=UpdateRole(_repository=repo, _cache=cache),
        list_permissions=ListPermissions(_repository=repo),
        create_permission=CreatePermission(_repository=repo),
        assign_role_permission=AssignRolePermission(_repository=repo, _cache=cache),
        remove_role_permission=RemoveRolePermission(_repository=repo, _cache=cache),
        assign_user_role=AssignUserRole(_repository=repo, _cache=cache),
        remove_user_role=RemoveUserRole(_repository=repo, _cache=cache),
        list_audit_events=ListAuditEvents(_repository=repo),
        seed_initial_data=seed,
        bootstrap_super_admin=BootstrapSuperAdmin(
            _repository=repo,
            _seed=seed,
            _register_user=register_user,
            _cache=cache,
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
