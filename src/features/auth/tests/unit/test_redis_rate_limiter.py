"""Unit tests for :class:`RedisRateLimiter`, backed by ``fakeredis``.

Using ``fakeredis`` lets the suite exercise real Redis semantics
(``INCR`` / ``EXPIRE``) without requiring a running Redis server, so the
tests stay fast and self-contained on any developer machine and CI runner.
"""

from __future__ import annotations

import fakeredis
import pytest

from src.features.auth.application.errors import RateLimitExceededError
from src.features.auth.application.rate_limit import RedisRateLimiter

pytestmark = pytest.mark.unit


def _limiter(max_attempts: int = 3, window_seconds: int = 60) -> RedisRateLimiter:
    """Build a limiter wired to a fresh in-process fake Redis client."""
    client = fakeredis.FakeRedis()
    return RedisRateLimiter(
        client, max_attempts=max_attempts, window_seconds=window_seconds
    )


def test_attempts_within_limit_are_allowed() -> None:
    limiter = _limiter(max_attempts=3)
    limiter.check("client")
    limiter.check("client")
    limiter.check("client")


def test_exceeding_limit_raises_rate_limit_error() -> None:
    limiter = _limiter(max_attempts=2)
    limiter.check("client")
    limiter.check("client")

    with pytest.raises(RateLimitExceededError):
        limiter.check("client")


def test_different_keys_have_independent_counters() -> None:
    limiter = _limiter(max_attempts=1)
    limiter.check("client-a")

    # client-b owns its own counter, so this call must not raise.
    limiter.check("client-b")


def test_reset_clears_all_counters() -> None:
    limiter = _limiter(max_attempts=1)
    limiter.check("client")
    limiter.reset()

    limiter.check("client")


def test_window_expiry_allows_new_attempts() -> None:
    client = fakeredis.FakeRedis()
    limiter = RedisRateLimiter(client, max_attempts=1, window_seconds=1)
    limiter.check("client")

    # fakeredis does not advance real time, so we simulate window expiry
    # by deleting the key directly to verify the limiter recovers.
    client.delete("rate:client")
    limiter.check("client")


def test_two_limiter_instances_share_redis_global_counter() -> None:
    """Two app instances sharing one Redis enforce a combined cap (replica scenario)."""
    shared = fakeredis.FakeRedis(decode_responses=False)
    limiter_a = RedisRateLimiter(shared, max_attempts=3, window_seconds=60)
    limiter_b = RedisRateLimiter(shared, max_attempts=3, window_seconds=60)
    limiter_a.check("client")
    limiter_a.check("client")
    limiter_b.check("client")

    with pytest.raises(RateLimitExceededError):
        limiter_b.check("client")
