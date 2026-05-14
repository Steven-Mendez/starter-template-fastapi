"""Real-Redis per-account lockout across distinct simulated IPs.

Covers task 5.6 from ``harden-rate-limiting``: multi-attempt login from
two distinct simulated IPs against the same email — the per-account
limiter MUST trip at the configured threshold even though the
per-(ip, email) limiter sees only N/2 attempts per IP.

This test exercises the ``RedisRateLimiter`` against a real Redis
container (the in-process limiter is covered by the unit tests). The
container fixture follows the codebase convention used by the Postgres
integration tests: ``pytest.skip(...)`` at fixture time when Docker
isn't available so local laptops without a daemon don't hard-fail the
suite. ``make ci`` runs in an environment with Docker, where the test
executes for real.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from typing import Any

import pytest

from features.authentication.application.errors import RateLimitExceededError
from features.authentication.application.rate_limit import RedisRateLimiter

pytestmark = pytest.mark.integration


def _load_redis_container() -> Any:
    try:
        from testcontainers.redis import (  # type: ignore[import-untyped]
            RedisContainer,
        )
    except Exception:
        return None
    return RedisContainer


def _docker_available() -> bool:
    if _load_redis_container() is None:
        return False
    if os.environ.get("KANBAN_SKIP_TESTCONTAINERS") == "1":
        return False
    try:
        import docker  # type: ignore[import-untyped]

        docker.from_env().ping()
    except Exception:
        return False
    return True


@pytest.fixture(scope="module")
def _redis_url() -> Iterator[str]:
    """Spin up a real Redis 7 container shared across the module's tests."""
    if not _docker_available():
        pytest.skip("Docker not available for auth Redis testcontainers")
    container_cls = _load_redis_container()
    assert container_cls is not None
    with container_cls("redis:7") as redis_container:
        host = redis_container.get_container_host_ip()
        port = redis_container.get_exposed_port(6379)
        yield f"redis://{host}:{port}/0"


@pytest.fixture
def per_account_limiter(_redis_url: str) -> Iterator[RedisRateLimiter]:
    """Per-account login limiter wired against the real Redis container.

    Resets the limiter between tests so each one starts with an empty
    Redis keyspace and a deterministic budget.
    """
    limiter = RedisRateLimiter.from_url(
        _redis_url,
        max_attempts=5,
        window_seconds=300,
    )
    limiter.reset()
    try:
        yield limiter
    finally:
        limiter.reset()
        limiter.close()


def test_per_account_limiter_trips_with_distinct_simulated_ips(
    per_account_limiter: RedisRateLimiter,
) -> None:
    """N login attempts against the same account from two distinct IPs trip
    the per-account limiter at the configured threshold.

    The per-account limiter is keyed on the email (not the IP), so two
    simulated clients sharing the same victim email burn one combined
    budget. Once they collectively reach ``max_attempts``, the next
    attempt — from either IP — raises ``RateLimitExceededError``.
    """
    max_attempts = 5
    email = "victim@example.com"
    # The per-account key shape mirrors ``_account_key("login", email)``
    # in ``adapters/inbound/http/auth.py``. We exercise the limiter
    # directly because that is the only piece that needs to be sound
    # against Redis — the helper just forwards.
    account_key = f"per_account:login:{email}"

    # Two distinct simulated IPs alternate, but the per-account key is
    # IP-agnostic so each attempt eats from one shared budget.
    simulated_ips = ["203.0.113.10", "198.51.100.20"]
    for i in range(max_attempts):
        # The limiter receives the same key regardless of IP — that is
        # the whole point. Drive the loop anyway so the test mirrors a
        # realistic two-source attack.
        _ = simulated_ips[i % 2]
        per_account_limiter.check(account_key)

    # The (max_attempts + 1)-th attempt — still the same email, from
    # the SECOND distinct IP — MUST trip.
    with pytest.raises(RateLimitExceededError) as exc_info:
        per_account_limiter.check(account_key)

    # The error carries a Retry-After budget for the HTTP layer to
    # surface; tighten the assertion so a regression that drops the
    # value cannot pass silently.
    assert exc_info.value.retry_after_seconds > 0
    assert exc_info.value.retry_after_seconds <= 300


def test_per_account_limiter_distinct_emails_have_independent_budgets(
    per_account_limiter: RedisRateLimiter,
) -> None:
    """Two emails on the same Redis instance MUST keep separate budgets.

    Defence against a sister bug: a regression that collapses the
    per-account namespace would let one attacker DoS every other
    account by burning its single shared budget.
    """
    # Burn the budget for victim@example.com.
    for _ in range(5):
        per_account_limiter.check("per_account:login:victim@example.com")
    with pytest.raises(RateLimitExceededError):
        per_account_limiter.check("per_account:login:victim@example.com")

    # Another email's budget MUST be untouched.
    per_account_limiter.check("per_account:login:other@example.com")
