"""Integration tests for :func:`build_auth_container` rate limiter selection."""

from __future__ import annotations

import logging
from unittest.mock import patch

import fakeredis
import pytest
import redis as redis_lib

from app_platform.config.settings import AppSettings
from features.authentication.adapters.outbound.persistence.sqlmodel.repository import (
    SQLModelAuthRepository,
)
from features.authentication.application.cache import InProcessPrincipalCache
from features.authentication.application.rate_limit import (
    FixedWindowRateLimiter,
    RedisRateLimiter,
)
from features.authentication.composition.container import build_auth_container
from features.outbox.tests.fakes.fake_outbox import InlineDispatchOutboxUnitOfWork
from features.users.adapters.outbound.persistence.sqlmodel.repository import (
    SQLModelUserRepository,
)

pytestmark = pytest.mark.unit


def _noop_outbox_uow() -> InlineDispatchOutboxUnitOfWork:
    return InlineDispatchOutboxUnitOfWork(dispatcher=lambda _n, _p: None)


def test_build_auth_container_requires_jwt_secret(
    test_settings: AppSettings,
    sqlite_auth_repository: SQLModelAuthRepository,
    users_for_auth: SQLModelUserRepository,
) -> None:
    settings = test_settings.model_copy(update={"auth_jwt_secret_key": None})

    with pytest.raises(RuntimeError, match="APP_AUTH_JWT_SECRET_KEY"):
        build_auth_container(
            settings=settings,
            users=users_for_auth,
            outbox_uow=_noop_outbox_uow(),
            repository=sqlite_auth_repository,
        )


def test_build_auth_container_rejects_invalid_jwt_algorithm(
    test_settings: AppSettings,
    sqlite_auth_repository: SQLModelAuthRepository,
    users_for_auth: SQLModelUserRepository,
) -> None:
    settings = test_settings.model_copy(update={"auth_jwt_algorithm": "none"})

    with pytest.raises(ValueError, match="APP_AUTH_JWT_ALGORITHM"):
        build_auth_container(
            settings=settings,
            users=users_for_auth,
            outbox_uow=_noop_outbox_uow(),
            repository=sqlite_auth_repository,
        )


def test_build_auth_container_warns_for_unimplemented_oauth_settings(
    test_settings: AppSettings,
    sqlite_auth_repository: SQLModelAuthRepository,
    users_for_auth: SQLModelUserRepository,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(
        logging.WARNING, logger="features.authentication.composition.container"
    )
    settings = test_settings.model_copy(update={"auth_oauth_enabled": True})

    container = build_auth_container(
        settings=settings,
        users=users_for_auth,
        outbox_uow=_noop_outbox_uow(),
        repository=sqlite_auth_repository,
    )

    assert "event=auth.oauth.unimplemented" in caplog.text
    container.shutdown()


def test_build_auth_container_uses_fixed_limiter_without_redis_url(
    test_settings: AppSettings,
    sqlite_auth_repository: SQLModelAuthRepository,
    users_for_auth: SQLModelUserRepository,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """No ``auth_redis_url`` keeps the historical in-process limiter."""
    caplog.set_level(
        logging.ERROR, logger="features.authentication.composition.container"
    )
    settings = test_settings.model_copy(update={"auth_redis_url": None})
    container = build_auth_container(
        settings=settings,
        users=users_for_auth,
        outbox_uow=_noop_outbox_uow(),
        repository=sqlite_auth_repository,
    )
    assert isinstance(container.rate_limiter, FixedWindowRateLimiter)
    assert "event=auth.rate_limit.degraded" in caplog.text
    container.shutdown()


def test_build_auth_container_uses_configured_principal_cache_ttl(
    test_settings: AppSettings,
    sqlite_auth_repository: SQLModelAuthRepository,
    users_for_auth: SQLModelUserRepository,
) -> None:
    settings = test_settings.model_copy(
        update={"auth_redis_url": None, "auth_principal_cache_ttl_seconds": 5}
    )
    container = build_auth_container(
        settings=settings,
        users=users_for_auth,
        outbox_uow=_noop_outbox_uow(),
        repository=sqlite_auth_repository,
    )

    assert isinstance(container.principal_cache, InProcessPrincipalCache)
    assert container.principal_cache._cache.ttl == 5
    container.shutdown()


def test_build_auth_container_can_require_distributed_rate_limit(
    test_settings: AppSettings,
    sqlite_auth_repository: SQLModelAuthRepository,
    users_for_auth: SQLModelUserRepository,
) -> None:
    """In production, ``require_distributed_rate_limit`` without Redis raises.

    The production validator
    (:meth:`AuthenticationSettings.validate_production`) is the spec-aligned
    refusal point; the container check is defense-in-depth so a misconfigured
    production image never boots into a single-process limiter.
    """
    settings = test_settings.model_copy(
        update={
            "environment": "production",
            "auth_redis_url": None,
            "auth_require_distributed_rate_limit": True,
        }
    )
    with pytest.raises(RuntimeError, match="APP_AUTH_REQUIRE_DISTRIBUTED_RATE_LIMIT"):
        build_auth_container(
            settings=settings,
            users=users_for_auth,
            outbox_uow=_noop_outbox_uow(),
            repository=sqlite_auth_repository,
        )


def test_build_auth_container_falls_back_to_in_process_outside_production(
    test_settings: AppSettings,
    sqlite_auth_repository: SQLModelAuthRepository,
    users_for_auth: SQLModelUserRepository,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Dev/test boots without Redis even when the default-True flag is on.

    Regression guard: ``harden-rate-limiting`` flipped
    ``auth_require_distributed_rate_limit`` to ``True`` by default. Without
    this carve-out, ``docker-smoke`` (which sets ``APP_ENVIRONMENT=development``
    and no Redis) refuses to start. Production is still gated by the
    sibling :func:`test_build_auth_container_can_require_distributed_rate_limit`.
    """
    caplog.set_level(
        logging.WARNING, logger="features.authentication.composition.container"
    )
    settings = test_settings.model_copy(
        update={
            "environment": "development",
            "auth_redis_url": None,
            "auth_require_distributed_rate_limit": True,
        }
    )
    container = build_auth_container(
        settings=settings,
        users=users_for_auth,
        outbox_uow=_noop_outbox_uow(),
        repository=sqlite_auth_repository,
    )
    assert isinstance(container.rate_limiter, FixedWindowRateLimiter)
    assert "event=auth.rate_limiter.fallback_in_process" in caplog.text
    container.shutdown()


def test_build_auth_container_uses_redis_limiter_when_url_configured(
    test_settings: AppSettings,
    sqlite_auth_repository: SQLModelAuthRepository,
    users_for_auth: SQLModelUserRepository,
) -> None:
    """With ``auth_redis_url`` set, wiring uses ``RedisRateLimiter`` (fake Redis)."""
    settings = test_settings.model_copy(
        update={"auth_redis_url": "redis://placeholder:6379/0"},
    )
    fake = fakeredis.FakeRedis(decode_responses=False)
    with patch(
        "features.authentication.application.rate_limit.redis_lib.Redis.from_url",
        return_value=fake,
    ):
        container = build_auth_container(
            settings=settings,
            users=users_for_auth,
            outbox_uow=_noop_outbox_uow(),
            repository=sqlite_auth_repository,
        )
    assert isinstance(container.rate_limiter, RedisRateLimiter)
    container.shutdown()


def test_build_auth_container_propagates_redis_connection_failure(
    test_settings: AppSettings,
    sqlite_auth_repository: SQLModelAuthRepository,
    users_for_auth: SQLModelUserRepository,
) -> None:
    """Unreachable Redis at construction must fail loudly (no silent fallback)."""
    settings = test_settings.model_copy(
        update={"auth_redis_url": "redis://127.0.0.1:1/0"},
    )
    with (
        patch(
            "features.authentication.application.rate_limit.redis_lib.Redis.from_url",
            side_effect=redis_lib.ConnectionError("Connection refused"),
        ),
        pytest.raises(redis_lib.ConnectionError),
    ):
        build_auth_container(
            settings=settings,
            users=users_for_auth,
            outbox_uow=_noop_outbox_uow(),
            repository=sqlite_auth_repository,
        )
