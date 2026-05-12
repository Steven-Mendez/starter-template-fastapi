"""Rate limiters for auth endpoints.

Two interchangeable implementations are provided: an in-process fixed-window
limiter for single-instance deployments and a Redis-backed sliding-window
limiter for horizontally scaled deployments. Both expose the same
``check(key)`` contract so the application layer can swap them via
configuration.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import cast

import redis as redis_lib

from src.features.authentication.application.errors import RateLimitExceededError

# Lua script: atomic sliding-window check using a sorted set.
#
# Arguments:
#   KEYS[1]  - the rate-limit key (e.g. "rate:/auth/login:1.2.3.4:user@x.com")
#   ARGV[1]  - current time in milliseconds (integer)
#   ARGV[2]  - window size in milliseconds (integer)
#   ARGV[3]  - max allowed attempts (integer)
#   ARGV[4]  - unique member for this attempt (prevents duplicate scores)
#
# Returns: 1 if rate-limited, 0 if allowed.
_SLIDING_WINDOW_SCRIPT = """
local key        = KEYS[1]
local now_ms     = tonumber(ARGV[1])
local window_ms  = tonumber(ARGV[2])
local max_att    = tonumber(ARGV[3])
local member     = ARGV[4]
local window_ttl = math.ceil(window_ms / 1000)

redis.call('ZREMRANGEBYSCORE', key, 0, now_ms - window_ms)
local count = redis.call('ZCARD', key)
if count >= max_att then
    return 1
end
redis.call('ZADD', key, now_ms, member)
redis.call('EXPIRE', key, window_ttl)
return 0
"""


@dataclass(slots=True)
class FixedWindowRateLimiter:
    """In-process fixed-window rate limiter.

    Counts attempts per key in a local dictionary. Suitable for single-instance
    deployments only.

    WARNING: This limiter is NOT distributed. In horizontally scaled
    (multi-replica) deployments each replica maintains an independent counter,
    so the effective rate limit is max_attempts * num_replicas. Set
    APP_AUTH_REDIS_URL to use RedisRateLimiter for global enforcement.

    Attributes:
        max_attempts: Maximum number of allowed attempts within the window.
        window_seconds: Duration of the counting window in seconds.
    """

    max_attempts: int = 5
    window_seconds: int = 60
    _attempts: dict[str, list[float]] = field(default_factory=dict)

    def check(self, key: str) -> None:
        """Record one attempt for key and raise if the limit is exceeded.

        Args:
            key: Unique identifier for the client being rate-limited
                 (e.g. ``"path:ip:email"``).

        Raises:
            RateLimitExceededError: When the number of attempts within the
                current window reaches or exceeds ``max_attempts``.
        """
        now = time.monotonic()
        window_start = now - self.window_seconds
        attempts = [ts for ts in self._attempts.get(key, []) if ts >= window_start]
        if len(attempts) >= self.max_attempts:
            self._attempts[key] = attempts
            raise RateLimitExceededError("Rate limit exceeded")
        attempts.append(now)
        self._attempts[key] = attempts

    def reset(self) -> None:
        """Clear all in-memory attempt counters.

        Intended for use in tests to restore a clean state between cases.
        """
        self._attempts.clear()

    def close(self) -> None:
        """No-op so FixedWindowRateLimiter matches RedisRateLimiter's interface."""
        pass


class RedisRateLimiter:
    """Distributed sliding-window rate limiter backed by Redis.

    Uses a sorted set per key and an atomic Lua script to count attempts
    within a rolling time window. All replicas share the same counters,
    so the limit applies globally across the entire deployment.

    The sliding window is more accurate than a fixed window: it prevents
    double-rate-limit bursts at window boundaries (e.g. 5 requests at the
    end of one window + 5 at the start of the next would both be allowed
    by a fixed window, but blocked here).
    """

    def __init__(
        self,
        client: redis_lib.Redis,  # type: ignore[type-arg]
        *,
        max_attempts: int = 5,
        window_seconds: int = 60,
    ) -> None:
        """Initialise with an existing Redis client.

        Prefer ``from_url`` for production use. This constructor is intended
        for testing with injected clients such as ``fakeredis.FakeRedis``.

        Args:
            client: A connected ``redis.Redis`` instance.
            max_attempts: Maximum allowed attempts within the window.
            window_seconds: Duration of each counting window in seconds.
        """
        self._client = client
        self._max_attempts = max_attempts
        self._window_ms = window_seconds * 1000

    @classmethod
    def from_url(
        cls,
        url: str,
        *,
        max_attempts: int = 5,
        window_seconds: int = 60,
    ) -> "RedisRateLimiter":
        """Create a limiter by connecting to a Redis URL and verifying the connection.

        Args:
            url: Redis connection URL (e.g. ``"redis://localhost:6379/0"``).
            max_attempts: Maximum allowed attempts within the window.
            window_seconds: Duration of each counting window in seconds.

        Returns:
            A ready-to-use ``RedisRateLimiter`` instance.

        Raises:
            redis.exceptions.ConnectionError: If the Redis server is not reachable.
        """
        client: redis_lib.Redis = redis_lib.Redis.from_url(url, decode_responses=False)  # type: ignore[type-arg]
        # Ping at construction so a misconfigured URL fails loudly at startup
        # rather than silently on the first auth request.
        client.ping()
        return cls(client, max_attempts=max_attempts, window_seconds=window_seconds)

    def check(self, key: str) -> None:
        """Record one attempt for key and raise if the limit is exceeded.

        The check-and-record operation is atomic via a Lua script, so there
        are no race conditions between concurrent requests.

        Args:
            key: Unique identifier for the client being rate-limited
                 (e.g. ``"path:ip:email"``).

        Raises:
            RateLimitExceededError: When the attempt count within the current
                sliding window exceeds ``max_attempts``.
        """
        now_ms = int(time.time() * 1000)
        member = f"{now_ms}:{uuid.uuid4()}"
        result = cast(
            int,
            self._client.eval(
                _SLIDING_WINDOW_SCRIPT,
                1,
                f"rate:{key}",
                now_ms,
                self._window_ms,
                self._max_attempts,
                member,
            ),
        )
        if result == 1:
            raise RateLimitExceededError("Rate limit exceeded")

    def reset(self) -> None:
        """Delete all rate-limit keys from Redis.

        Intended for tests only; in production, keys expire automatically
        once the window elapses.
        """
        for key in self._client.scan_iter("rate:*"):
            self._client.delete(key)

    def close(self) -> None:
        """Close the underlying Redis connection.

        Should be called during application shutdown to release the connection.
        """
        self._client.close()
