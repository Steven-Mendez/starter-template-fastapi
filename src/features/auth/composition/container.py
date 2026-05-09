"""Composition root for the auth feature.

Builds and groups every collaborator (repository, services, rate limiter)
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
from src.features.auth.application.services import AuthService, RBACService
from src.platform.config.settings import AppSettings

_logger = logging.getLogger(__name__)

RateLimiter = Union[FixedWindowRateLimiter, RedisRateLimiter]


@dataclass(slots=True)
class AuthContainer:
    """Bundle of every collaborator the auth feature needs at runtime.

    Attributes:
        settings: Effective application settings.
        repository: Persistence adapter shared across services.
        auth_service: Use cases for user-facing auth flows.
        rbac_service: Use cases for role and permission management.
        rate_limiter: Either the in-process or the Redis-backed limiter,
            chosen based on configuration.
        shutdown: Callback invoked during application shutdown to release
            external resources (DB pool, Redis connection, ...). Modeled
            as a callback so the container does not need to know which
            specific resources require cleanup.
    """

    settings: AppSettings
    repository: SQLModelAuthRepository
    auth_service: AuthService
    rbac_service: RBACService
    rate_limiter: RateLimiter
    principal_cache: PrincipalCachePort
    shutdown: Callable[[], None]


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

    # Validate the JWT secret early so misconfiguration surfaces at startup
    # rather than on the first token issuance request.
    if not settings.auth_jwt_secret_key:
        raise RuntimeError("APP_AUTH_JWT_SECRET_KEY is required at startup")

    token_service = AccessTokenService(settings)
    _warn_unused_oauth_settings(settings)
    _check_internal_token_exposure(settings)

    # Select the rate limiter based on whether a Redis URL is configured.
    # RedisRateLimiter pings Redis at construction, so a bad URL fails here
    # rather than on the first auth request.
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

    def _shutdown() -> None:
        repo.close()
        limiter.close()
        cache.close()

    return AuthContainer(
        settings=settings,
        repository=repo,
        auth_service=AuthService(
            repository=repo,
            settings=settings,
            password_service=password_service,
            token_service=token_service,
            cache=cache,
        ),
        rbac_service=RBACService(repository=repo, cache=cache),
        rate_limiter=limiter,
        principal_cache=cache,
        shutdown=_shutdown,
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
        # Returning single-use tokens in API bodies short-circuits the email
        # delivery channel, so it must never reach production deployments.
        raise RuntimeError(
            "APP_AUTH_RETURN_INTERNAL_TOKENS=true is forbidden in production"
        )
    _logger.warning(
        "event=auth.internal_tokens.exposed environment=%s "
        "message=Password-reset and email-verify tokens will be returned in "
        "API responses; only acceptable for local development and e2e tests",
        settings.environment,
    )
