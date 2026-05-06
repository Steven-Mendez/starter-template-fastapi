"""Rate limiters for auth endpoints.

Two interchangeable implementations are provided: an in-process fixed-window
limiter for single-instance deployments and a Redis-backed limiter for
horizontally scaled deployments. Both expose the same ``check(key)``
contract so the application layer can swap them via configuration.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import cast

import redis as redis_lib

from src.features.auth.application.errors import RateLimitExceededError


@dataclass(slots=True)
class FixedWindowRateLimiter:
    """In-process fixed-window rate limiter.

    Counts attempts per key in a local dictionary. Suitable for single-instance
    deployments. For multi-instance deployments use RedisRateLimiter instead.

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
    """Distributed fixed-window rate limiter backed by Redis.

    Uses INCR + EXPIRE so all replicas share a single counter per key,
    making the limit apply globally across the whole deployment.
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
        self._window_seconds = window_seconds

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
        # decode_responses=False keeps bytes round-tripping consistent with
        # the INCR return type (int), avoiding extra decode/encode overhead.
        client: redis_lib.Redis = redis_lib.Redis.from_url(url, decode_responses=False)  # type: ignore[type-arg]
        # Ping at construction so a misconfigured URL fails loudly at startup
        # rather than silently on the first auth request.
        client.ping()
        return cls(client, max_attempts=max_attempts, window_seconds=window_seconds)

    def check(self, key: str) -> None:
        """Record one attempt for key and raise if the limit is exceeded.

        Args:
            key: Unique identifier for the client being rate-limited
                 (e.g. ``"path:ip:email"``).

        Raises:
            RateLimitExceededError: When the attempt count within the current
                window exceeds ``max_attempts``.
        """
        redis_key = f"rate:{key}"
        # Sync Redis client returns int; stubs may union with coroutine types.
        count = cast(int, self._client.incr(redis_key))
        if count == 1:
            # Set expiry only on the first increment so the window is anchored
            # at the first attempt, matching the in-memory limiter's behaviour.
            self._client.expire(redis_key, self._window_seconds)
        if count > self._max_attempts:
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
