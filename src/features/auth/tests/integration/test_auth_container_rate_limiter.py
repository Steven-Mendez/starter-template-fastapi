"""Integration tests for :func:`build_auth_container` rate limiter selection."""

from __future__ import annotations

from unittest.mock import patch

import fakeredis
import pytest
import redis as redis_lib

from src.features.auth.adapters.outbound.persistence.sqlmodel.repository import (
    SQLModelAuthRepository,
)
from src.features.auth.application.rate_limit import (
    FixedWindowRateLimiter,
    RedisRateLimiter,
)
from src.features.auth.composition.container import build_auth_container
from src.platform.config.settings import AppSettings

pytestmark = pytest.mark.unit


def test_build_auth_container_uses_fixed_limiter_without_redis_url(
    test_settings: AppSettings,
    sqlite_auth_repository: SQLModelAuthRepository,
) -> None:
    """No ``auth_redis_url`` keeps the historical in-process limiter."""
    settings = test_settings.model_copy(update={"auth_redis_url": None})
    container = build_auth_container(
        settings=settings, repository=sqlite_auth_repository
    )
    assert isinstance(container.rate_limiter, FixedWindowRateLimiter)
    container.shutdown()


def test_build_auth_container_uses_redis_limiter_when_url_configured(
    test_settings: AppSettings,
    sqlite_auth_repository: SQLModelAuthRepository,
) -> None:
    """With ``auth_redis_url`` set, wiring uses ``RedisRateLimiter`` (fake Redis)."""
    settings = test_settings.model_copy(
        update={"auth_redis_url": "redis://placeholder:6379/0"},
    )
    fake = fakeredis.FakeRedis(decode_responses=False)
    with patch(
        "src.features.auth.application.rate_limit.redis_lib.Redis.from_url",
        return_value=fake,
    ):
        container = build_auth_container(
            settings=settings, repository=sqlite_auth_repository
        )
    assert isinstance(container.rate_limiter, RedisRateLimiter)
    container.shutdown()


def test_build_auth_container_propagates_redis_connection_failure(
    test_settings: AppSettings,
    sqlite_auth_repository: SQLModelAuthRepository,
) -> None:
    """Unreachable Redis at construction must fail loudly (no silent fallback)."""
    settings = test_settings.model_copy(
        update={"auth_redis_url": "redis://127.0.0.1:1/0"},
    )
    with (
        patch(
            "src.features.auth.application.rate_limit.redis_lib.Redis.from_url",
            side_effect=redis_lib.ConnectionError("Connection refused"),
        ),
        pytest.raises(redis_lib.ConnectionError),
    ):
        build_auth_container(settings=settings, repository=sqlite_auth_repository)
