"""Composition root for the auth feature.

Builds and groups every collaborator (repository, services, rate limiter)
in a single container so the rest of the application receives a single
object instead of dozens of individual dependencies. Tests construct
their own container with substitute components when they need to swap
behaviour.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Union

from src.features.auth.adapters.outbound.persistence.sqlmodel import (
    SQLModelAuthRepository,
)
from src.features.auth.application.crypto import PasswordService
from src.features.auth.application.jwt_tokens import AccessTokenService
from src.features.auth.application.rate_limit import (
    FixedWindowRateLimiter,
    RedisRateLimiter,
)
from src.features.auth.application.services import AuthService, RBACService
from src.platform.config.settings import AppSettings

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
        settings.postgresql_dsn, create_schema=False
    )
    password_service = PasswordService()
    token_service = AccessTokenService(settings)

    # Select the rate limiter based on whether a Redis URL is configured.
    # RedisRateLimiter pings Redis at construction, so a bad URL fails here
    # rather than on the first auth request.
    limiter: RateLimiter
    if settings.auth_redis_url:
        limiter = RedisRateLimiter.from_url(settings.auth_redis_url)
    else:
        limiter = FixedWindowRateLimiter()

    def _shutdown() -> None:
        repo.close()
        limiter.close()

    return AuthContainer(
        settings=settings,
        repository=repo,
        auth_service=AuthService(
            repository=repo,
            settings=settings,
            password_service=password_service,
            token_service=token_service,
        ),
        rbac_service=RBACService(repository=repo),
        rate_limiter=limiter,
        shutdown=_shutdown,
    )
