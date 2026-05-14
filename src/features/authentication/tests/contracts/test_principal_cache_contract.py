"""Bind :class:`PrincipalCacheContract` to every shipping cache backend.

The in-process cache binds straight against the real backend.
``RedisPrincipalCache`` binds via ``fakeredis`` so the Redis-side
serialisation round-trip is exercised on every ``make test`` invocation
even without Docker.
"""

from __future__ import annotations

from typing import Any, ClassVar

import fakeredis
import pytest

from features.authentication.application.cache import (
    InProcessPrincipalCache,
    RedisPrincipalCache,
)
from features.authentication.tests.contracts.principal_cache_contract import (
    PrincipalCacheContract,
)


class TestInProcessPrincipalCacheContract(PrincipalCacheContract):
    pytestmark: ClassVar = [pytest.mark.unit]

    def _make_cache(self, *, ttl: int = 60) -> InProcessPrincipalCache:
        return InProcessPrincipalCache.create(maxsize=100, ttl=ttl)


class TestFakeRedisPrincipalCacheContract(PrincipalCacheContract):
    pytestmark: ClassVar = [pytest.mark.unit]

    def _make_cache(self, *, ttl: int = 60) -> RedisPrincipalCache:
        # The cache class uses ``@dataclass(slots=True)``; the ``_redis``
        # field already names the client, so ``_advance_past_ttl``
        # reaches into it directly rather than stashing a sidecar.
        client = fakeredis.FakeRedis(lua_modules=set())
        return RedisPrincipalCache(_redis=client, _ttl=ttl)

    def _advance_past_ttl(self, cache: Any, ttl: int) -> None:
        # ``fakeredis`` does not honour ``SETEX`` expiry on real time
        # progression, so we delete every ``auth:principal:*`` key to
        # simulate the TTL elapsing — same trick the redis rate
        # limiter unit suite uses for the analogous test.
        client = cache._redis
        for key in list(client.scan_iter("auth:principal:*")):
            client.delete(key)
        for key in list(client.scan_iter("auth:user_tokens:*")):
            client.delete(key)
