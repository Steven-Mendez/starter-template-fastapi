"""``RateLimitExceededError`` carries a positive ``retry_after_seconds`` budget.

The HTTP error mapping reads this off the error and sets it as the
``Retry-After`` header on the 429 response, so the value MUST be:

- present (never None),
- a positive integer,
- bounded by the limiter's configured window.
"""

from __future__ import annotations

import pickle

import fakeredis
import pytest

from features.authentication.application.errors import RateLimitExceededError
from features.authentication.application.rate_limit import (
    FixedWindowRateLimiter,
    RedisRateLimiter,
)

pytestmark = pytest.mark.unit


def test_fixed_window_limiter_sets_positive_retry_after() -> None:
    limiter = FixedWindowRateLimiter(max_attempts=1, window_seconds=60)
    limiter.check("client")

    with pytest.raises(RateLimitExceededError) as exc_info:
        limiter.check("client")

    assert exc_info.value.retry_after_seconds > 0
    assert exc_info.value.retry_after_seconds <= 60


def test_redis_limiter_sets_positive_retry_after() -> None:
    client = fakeredis.FakeRedis(lua_modules=set())
    limiter = RedisRateLimiter(client, max_attempts=1, window_seconds=30)
    limiter.check("client")

    with pytest.raises(RateLimitExceededError) as exc_info:
        limiter.check("client")

    assert exc_info.value.retry_after_seconds > 0
    assert exc_info.value.retry_after_seconds <= 30


def test_rate_limit_error_round_trips_through_pickle() -> None:
    """Required so the error round-trips across a serializing job-runtime
    boundary (the future AWS SQS + Lambda worker)."""
    original = RateLimitExceededError("Rate limit exceeded", retry_after_seconds=42)

    restored = pickle.loads(pickle.dumps(original))

    assert type(restored) is RateLimitExceededError
    assert str(restored) == str(original)
    assert restored.retry_after_seconds == 42
