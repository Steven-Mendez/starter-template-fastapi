"""Bind :class:`RateLimiterContract` to every shipping rate-limiter.

Three bindings:

* ``FixedWindowRateLimiter`` — in-process, ``time.monotonic``-driven.
* ``RedisRateLimiter`` against ``fakeredis`` — unit-marker, no Docker.
* ``RedisRateLimiter`` against testcontainers Redis — integration-marker,
  skipped when Docker is unavailable. Exercising the contract against a
  real Redis catches Lua-script regressions ``fakeredis`` cannot model.
"""

from __future__ import annotations

import os
from typing import Any, ClassVar

import fakeredis
import pytest

from features.authentication.application.rate_limit import (
    FixedWindowRateLimiter,
    RedisRateLimiter,
)
from features.authentication.tests.contracts.rate_limiter_contract import (
    RateLimiterContract,
)


class TestFixedWindowRateLimiterContract(RateLimiterContract):
    pytestmark: ClassVar = [pytest.mark.unit]

    def _make_limiter(
        self, *, max_attempts: int = 3, window_seconds: int = 60
    ) -> FixedWindowRateLimiter:
        return FixedWindowRateLimiter(
            max_attempts=max_attempts, window_seconds=window_seconds
        )


class TestFakeRedisRateLimiterContract(RateLimiterContract):
    pytestmark: ClassVar = [pytest.mark.unit]

    def _make_limiter(
        self, *, max_attempts: int = 3, window_seconds: int = 60
    ) -> RedisRateLimiter:
        # Disable Lua module compilation so ``EVAL`` runs the inlined
        # sliding-window script directly — matches the unit suite's
        # existing ``fakeredis`` setup.
        client = fakeredis.FakeRedis(lua_modules=set())
        return RedisRateLimiter(
            client, max_attempts=max_attempts, window_seconds=window_seconds
        )

    def _advance_window(self, limiter: Any, window_seconds: int) -> None:
        # ``fakeredis`` does not advance real time, so we simulate window
        # expiry by deleting the rate-limit key directly. This matches
        # ``test_window_expiry_allows_new_attempts`` in the existing
        # unit suite. The ``_client`` private attribute is the same one
        # the production ``reset()`` path reaches into.
        client = limiter._client
        for key in list(client.scan_iter("rate:*")):
            client.delete(key)


def _docker_available_for_redis() -> bool:
    """True iff a real Redis can be started via testcontainers."""
    if os.environ.get("KANBAN_SKIP_TESTCONTAINERS") == "1":
        return False
    try:
        from testcontainers.redis import (  # type: ignore[import-untyped]  # noqa: F401
            RedisContainer,
        )
    except Exception:
        return False
    try:
        import docker  # type: ignore[import-untyped]

        docker.from_env().ping()
    except Exception:
        return False
    return True


@pytest.fixture(scope="session")
def _redis_url() -> Any:
    if not _docker_available_for_redis():
        pytest.skip("Docker / testcontainers Redis not available")
    from testcontainers.redis import (
        RedisContainer,
    )

    with RedisContainer("redis:7") as container:
        host = container.get_container_host_ip()
        port = container.get_exposed_port(6379)
        yield f"redis://{host}:{port}/0"


class TestRealRedisRateLimiterContract(RateLimiterContract):
    """Run the contract against a real ``redis:7`` testcontainer.

    Catches Lua-script and atomicity regressions ``fakeredis`` cannot
    model (e.g. server-side ``EVAL`` semantics, key-encoding quirks).
    """

    pytestmark: ClassVar = [pytest.mark.integration]

    @pytest.fixture(autouse=True)
    def _bind_redis_url(self, _redis_url: str) -> None:
        # Inject the container URL onto ``self`` so ``_make_limiter`` can
        # see it without a parametrize indirection (the contract's
        # ``_make_limiter`` signature does not accept fixtures).
        self._redis_url = _redis_url

    def _make_limiter(
        self, *, max_attempts: int = 3, window_seconds: int = 60
    ) -> RedisRateLimiter:
        limiter = RedisRateLimiter.from_url(
            self._redis_url,
            max_attempts=max_attempts,
            window_seconds=window_seconds,
        )
        # Clear any leftover state from a previous test in the session.
        limiter.reset()
        return limiter
