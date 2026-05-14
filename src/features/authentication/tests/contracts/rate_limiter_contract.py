"""Behavioural contract shared by every rate-limiter implementation.

The auth feature ships two limiters with deliberately different
algorithms (fixed window vs sliding window) but the same externally
observable behaviour: allow N attempts in a window, block N+1, recover
after the window passes, treat distinct keys independently, and clear
on ``reset()``. The contract pins exactly that surface so the two
implementations cannot silently diverge.

Sliding-window vs fixed-window timing nuances are exercised by the
implementation-specific unit tests; the contract only asserts the
properties both algorithms must agree on.
"""

from __future__ import annotations

import time
from typing import Any, Protocol

import pytest

from features.authentication.application.errors import RateLimitExceededError


class _Limiter(Protocol):
    """Protocol the contract relies on (subset of the auth rate-limiter API)."""

    def check(self, key: str) -> None: ...
    def reset(self) -> None: ...


class RateLimiterContract:
    """Subclass and override ``_make_limiter``.

    ``max_attempts`` and ``window_seconds`` are passed through so each
    binding can configure its own backend the same way the production
    composition does.
    """

    def _make_limiter(self, *, max_attempts: int = 3, window_seconds: int = 60) -> Any:
        raise NotImplementedError

    def _advance_window(self, limiter: Any, window_seconds: int) -> None:
        """Skip past ``window_seconds`` worth of elapsed time.

        Subclasses MAY override to advance the limiter's clock (e.g.
        ``fakeredis`` does not advance real time; the test deletes the
        Redis key directly to simulate window expiry). The default
        implementation sleeps just over one window — fine for the
        in-process limiter whose ``time.monotonic`` source is real.
        """
        time.sleep(window_seconds + 0.05)

    # ── Scenarios ─────────────────────────────────────────────────────────────

    def test_allow_n_attempts_in_window(self) -> None:
        limiter = self._make_limiter(max_attempts=3, window_seconds=60)
        limiter.check("client")
        limiter.check("client")
        limiter.check("client")

    def test_block_attempt_n_plus_one(self) -> None:
        limiter = self._make_limiter(max_attempts=2, window_seconds=60)
        limiter.check("client")
        limiter.check("client")
        with pytest.raises(RateLimitExceededError):
            limiter.check("client")

    def test_distinct_keys_are_independent(self) -> None:
        limiter = self._make_limiter(max_attempts=1, window_seconds=60)
        limiter.check("client-a")
        # ``client-b`` has its own budget — must NOT raise.
        limiter.check("client-b")

    def test_recover_after_window_passes(self) -> None:
        limiter = self._make_limiter(max_attempts=1, window_seconds=1)
        limiter.check("client")
        with pytest.raises(RateLimitExceededError):
            limiter.check("client")
        self._advance_window(limiter, window_seconds=1)
        # After the window expires the budget MUST reset and the next
        # attempt MUST succeed.
        limiter.check("client")

    def test_reset_clears_all_keys(self) -> None:
        limiter = self._make_limiter(max_attempts=1, window_seconds=60)
        limiter.check("client-a")
        limiter.check("client-b")
        with pytest.raises(RateLimitExceededError):
            limiter.check("client-a")
        limiter.reset()
        # After reset both keys' budgets are clear.
        limiter.check("client-a")
        limiter.check("client-b")
