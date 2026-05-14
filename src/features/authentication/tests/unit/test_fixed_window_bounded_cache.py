"""Bounded-cache contract for :class:`FixedWindowRateLimiter`.

Covers tasks 3.2 and 5.3 from ``harden-rate-limiting``. The in-process
limiter MUST evict LRU entries once its ``maxsize`` is reached so an
attacker cycling through rate-limit keys (rotating IPs / emails) cannot
turn the limiter into a memory-exhaustion vector.

The previous implementation stored attempts in an unbounded ``dict`` —
distinct keys grew the structure without bound. The fix is a
``cachetools.TTLCache`` capped at ``maxsize`` keys, asserted here.
"""

from __future__ import annotations

import pytest

from features.authentication.application.rate_limit import FixedWindowRateLimiter

pytestmark = pytest.mark.unit


def test_cache_size_never_exceeds_maxsize_with_small_cap() -> None:
    """Task 5.3: ``maxsize=10`` cap holds even when 100 distinct keys are seen."""
    limiter = FixedWindowRateLimiter(
        max_attempts=5,
        window_seconds=60,
        maxsize=10,
    )

    for i in range(100):
        limiter.check(f"key-{i}")
        # The cache MUST never grow past the configured maxsize, even
        # transiently, between ``check`` calls.
        assert len(limiter._attempts) <= 10, (
            f"cache size {len(limiter._attempts)} exceeded maxsize=10 "
            f"after inserting key-{i}"
        )

    assert len(limiter._attempts) <= 10


def test_cache_size_never_exceeds_maxsize_under_heavy_load() -> None:
    """Task 3.2: >10k distinct keys against a maxsize-capped limiter stay bounded.

    Uses a smaller maxsize (1_000) to keep the test fast while still
    exercising the eviction path with an order-of-magnitude more keys
    than the cap allows.
    """
    cap = 1_000
    limiter = FixedWindowRateLimiter(
        max_attempts=5,
        window_seconds=60,
        maxsize=cap,
    )

    # Twelve thousand distinct keys — well past the cap, comfortably
    # over the 10k requirement quoted in the spec.
    total_keys = 12_000
    for i in range(total_keys):
        limiter.check(f"key-{i}")

    # The cache should be exactly capped at ``maxsize`` after the load
    # — every insertion beyond ``cap`` evicts an older entry.
    assert len(limiter._attempts) <= cap


def test_default_maxsize_matches_documented_bound() -> None:
    """The default ``maxsize`` is the documented 10 000 bound."""
    limiter = FixedWindowRateLimiter()
    assert limiter._attempts.maxsize == 10_000


def test_eviction_does_not_leak_attempt_lists() -> None:
    """Once a key is evicted, the limiter must not retain its attempt list.

    Sanity check: ``TTLCache`` already guarantees this, but the test
    pins the behaviour so a future swap to a different cache type that
    keeps a side-buffer would fail loudly.
    """
    limiter = FixedWindowRateLimiter(
        max_attempts=5,
        window_seconds=60,
        maxsize=3,
    )
    for i in range(10):
        limiter.check(f"key-{i}")

    # No more than ``maxsize`` keys remain.
    assert len(limiter._attempts) <= 3
    # The earliest keys must have been evicted.
    remaining = set(limiter._attempts.keys())
    assert "key-0" not in remaining
    assert "key-1" not in remaining
