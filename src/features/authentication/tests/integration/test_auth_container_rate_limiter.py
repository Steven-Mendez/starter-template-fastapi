"""Integration tests for :func:`build_auth_container` rate limiter selection."""

from __future__ import annotations

import logging
from unittest.mock import patch

import fakeredis
import pytest
import redis as redis_lib

from src.features.authentication.adapters.outbound.persistence.sqlmodel.repository import (  # noqa: E501
    SQLModelAuthRepository,
)
from src.features.authentication.application.cache import InProcessPrincipalCache
from src.features.authentication.application.rate_limit import (
    FixedWindowRateLimiter,
    RedisRateLimiter,
)
from src.features.authentication.composition.container import build_auth_container
from src.features.outbox.tests.fakes.fake_outbox import InlineDispatchOutboxAdapter
from src.features.users.adapters.outbound.persistence.sqlmodel.repository import (
    SQLModelUserRepository,
)
from src.platform.config.settings import AppSettings

pytestmark = pytest.mark.unit


def _noop_outbox_factory(_session: object) -> InlineDispatchOutboxAdapter:
    return InlineDispatchOutboxAdapter(dispatcher=lambda _n, _p: None)


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
            outbox_session_factory=_noop_outbox_factory,
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
            outbox_session_factory=_noop_outbox_factory,
            repository=sqlite_auth_repository,
        )


def test_build_auth_container_warns_for_unimplemented_oauth_settings(
    test_settings: AppSettings,
    sqlite_auth_repository: SQLModelAuthRepository,
    users_for_auth: SQLModelUserRepository,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(
        logging.WARNING, logger="src.features.authentication.composition.container"
    )
    settings = test_settings.model_copy(update={"auth_oauth_enabled": True})

    container = build_auth_container(
        settings=settings,
        users=users_for_auth,
        outbox_session_factory=_noop_outbox_factory,
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
        logging.ERROR, logger="src.features.authentication.composition.container"
    )
    settings = test_settings.model_copy(update={"auth_redis_url": None})
    container = build_auth_container(
        settings=settings,
        users=users_for_auth,
        outbox_session_factory=_noop_outbox_factory,
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
        outbox_session_factory=_noop_outbox_factory,
        repository=sqlite_auth_repository,
    )

    assert isinstance(container.principal_cache, InProcessPrincipalCache)
    assert container.principal_cache._cache.ttl == 5  # noqa: SLF001
    container.shutdown()


def test_build_auth_container_can_require_distributed_rate_limit(
    test_settings: AppSettings,
    sqlite_auth_repository: SQLModelAuthRepository,
    users_for_auth: SQLModelUserRepository,
) -> None:
    settings = test_settings.model_copy(
        update={
            "auth_redis_url": None,
            "auth_require_distributed_rate_limit": True,
        }
    )
    with pytest.raises(RuntimeError, match="APP_AUTH_REQUIRE_DISTRIBUTED_RATE_LIMIT"):
        build_auth_container(
            settings=settings,
            users=users_for_auth,
            outbox_session_factory=_noop_outbox_factory,
            repository=sqlite_auth_repository,
        )


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
        "src.features.authentication.application.rate_limit.redis_lib.Redis.from_url",
        return_value=fake,
    ):
        container = build_auth_container(
            settings=settings,
            users=users_for_auth,
            outbox_session_factory=_noop_outbox_factory,
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
            "src.features.authentication.application.rate_limit.redis_lib.Redis.from_url",
            side_effect=redis_lib.ConnectionError("Connection refused"),
        ),
        pytest.raises(redis_lib.ConnectionError),
    ):
        build_auth_container(
            settings=settings,
            users=users_for_auth,
            outbox_session_factory=_noop_outbox_factory,
            repository=sqlite_auth_repository,
        )
