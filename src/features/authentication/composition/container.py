"""Composition root for the auth feature.

Builds and groups every collaborator (repository, use cases, rate
limiter, principal cache) in a single container so the rest of the
application receives a single object instead of dozens of individual
dependencies. Tests construct their own container with substitute
components when they need to swap behaviour.

The authorization-feature ports auth implements
(``UserAuthzVersionPort``, ``UserRegistrarPort``, ``AuditPort``) are
exposed on the container so the composition root can wire them into
the authorization container without crossing feature boundaries.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass

from app_platform.config.settings import AppSettings
from features.authentication.adapters.outbound.audit import SQLModelAuditAdapter
from features.authentication.adapters.outbound.credential_writer import (
    SQLModelCredentialWriterAdapter,
)
from features.authentication.adapters.outbound.persistence.sqlmodel import (
    SQLModelAuthRepository,
)
from features.authentication.application.cache import (
    InProcessPrincipalCache,
    PrincipalCachePort,
    RedisPrincipalCache,
)
from features.authentication.application.crypto import PasswordService
from features.authentication.application.jwt_tokens import AccessTokenService
from features.authentication.application.rate_limit import (
    FixedWindowRateLimiter,
    RedisRateLimiter,
)
from features.authentication.application.use_cases.admin.list_audit_events import (
    ListAuditEvents,
)
from features.authentication.application.use_cases.auth.confirm_email_verification import (  # noqa: E501
    ConfirmEmailVerification,
)
from features.authentication.application.use_cases.auth.confirm_password_reset import (
    ConfirmPasswordReset,
)
from features.authentication.application.use_cases.auth.login_user import LoginUser
from features.authentication.application.use_cases.auth.logout_user import (
    LogoutAllSessions,
    LogoutUser,
)
from features.authentication.application.use_cases.auth.refresh_token import (
    RotateRefreshToken,
)
from features.authentication.application.use_cases.auth.register_user import (
    RegisterUser,
)
from features.authentication.application.use_cases.auth.request_email_verification import (  # noqa: E501
    RequestEmailVerification,
)
from features.authentication.application.use_cases.auth.request_password_reset import (
    RequestPasswordReset,
)
from features.authentication.application.use_cases.auth.resolve_principal import (
    ResolvePrincipalFromAccessToken,
)
from features.outbox.application.ports.outbox_uow_port import OutboxUnitOfWorkPort
from features.users.application.ports.user_port import UserPort

_logger = logging.getLogger(__name__)

RateLimiter = FixedWindowRateLimiter | RedisRateLimiter


@dataclass(slots=True)
class AuthContainer:
    """Bundle of every collaborator the auth feature needs at runtime."""

    settings: AppSettings
    repository: SQLModelAuthRepository
    rate_limiter: RateLimiter
    principal_cache: PrincipalCachePort
    # Audit-log adapter the authorization feature uses to record authz.* events.
    audit_adapter: SQLModelAuditAdapter
    # Credential-writer adapter the users-feature registrar uses to write the
    # initial password for the bootstrap admin.
    credential_writer_adapter: SQLModelCredentialWriterAdapter
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
    list_audit_events: ListAuditEvents


def build_auth_container(
    *,
    settings: AppSettings,
    users: UserPort,
    outbox_uow: OutboxUnitOfWorkPort,
    repository: SQLModelAuthRepository | None = None,
) -> AuthContainer:
    """Wire all auth dependencies and return a ready-to-use container.

    ``outbox_uow`` is the transport-agnostic unit-of-work the
    repository uses inside ``issue_internal_token_transaction`` so the
    token write, audit event, and outbox row commit atomically. The
    Protocol-shaped seam keeps the producer wiring free of
    ``sqlmodel.Session`` (enforced by an Import Linter contract).
    """
    repo = repository or SQLModelAuthRepository(
        settings.postgresql_dsn,
        create_schema=False,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_recycle=settings.db_pool_recycle_seconds,
        pool_pre_ping=settings.db_pool_pre_ping,
        outbox_uow=outbox_uow,
    )
    # When the caller passes a pre-constructed repository (the typical
    # case: ``main.py`` builds the engine via the auth repo to share
    # one pool across features), the repository may not yet know about
    # the outbox UoW. Attach it now via the private slot — the
    # attribute is owned by this composition layer, not the test
    # surface, so there is no setter on the public API.
    if repository is not None:
        repo._outbox_uow = outbox_uow
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

    audit_adapter = SQLModelAuditAdapter(repo)
    credential_writer_adapter = SQLModelCredentialWriterAdapter(
        credentials=repo, password_service=password_service
    )

    register_user = RegisterUser(
        _users=users,
        _credentials=repo,
        _audit=repo,
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
        audit_adapter=audit_adapter,
        credential_writer_adapter=credential_writer_adapter,
        shutdown=_shutdown,
        register_user=register_user,
        login_user=LoginUser(
            _users=users,
            _repository=repo,
            _password_service=password_service,
            _token_service=token_service,
            _settings=settings,
            _dummy_hash=dummy_hash,
        ),
        rotate_refresh_token=RotateRefreshToken(
            _users=users,
            _repository=repo,
            _token_service=token_service,
            _settings=settings,
        ),
        logout_user=LogoutUser(_repository=repo, _cache=cache),
        logout_all_sessions=LogoutAllSessions(_repository=repo, _cache=cache),
        request_password_reset=RequestPasswordReset(
            _users=users,
            _repository=repo,
            _settings=settings,
        ),
        confirm_password_reset=ConfirmPasswordReset(
            _users=users,
            _repository=repo,
            _password_service=password_service,
            _cache=cache,
        ),
        request_email_verification=RequestEmailVerification(
            _users=users,
            _repository=repo,
            _settings=settings,
        ),
        confirm_email_verification=ConfirmEmailVerification(
            _users=users,
            _repository=repo,
            _cache=cache,
        ),
        resolve_principal=ResolvePrincipalFromAccessToken.create(
            users=users,
            token_service=token_service,
            settings=settings,
            cache=cache,
        ),
        list_audit_events=ListAuditEvents(_repository=repo),
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
