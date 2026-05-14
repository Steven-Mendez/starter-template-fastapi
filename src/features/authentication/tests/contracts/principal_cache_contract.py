"""Behavioural contract shared by every :class:`PrincipalCachePort`
implementation.

Pins the externally observable semantics every implementation must
agree on: round-trip set/get, TTL-driven expiry, ``invalidate_user``
removes all of that user's cached entries, and a miss returns
``None`` rather than raising. The two adapters that ship with the
template (``InProcessPrincipalCache`` and ``RedisPrincipalCache``)
parametrise against this contract so a divergence shows up as a single
test failure rather than as drift between the in-process and Redis
unit suites.
"""

from __future__ import annotations

import time
from typing import Any
from uuid import UUID, uuid4

from app_platform.shared.principal import Principal


def _principal(user_id: UUID | None = None, email: str = "u@example.com") -> Principal:
    return Principal(
        user_id=user_id or uuid4(),
        email=email,
        is_active=True,
        is_verified=True,
        authz_version=1,
    )


class PrincipalCacheContract:
    """Subclass and override ``_make_cache``.

    ``ttl`` is passed through so each binding can configure its backend
    the same way the production composition does. Subclasses MAY
    override ``_advance_past_ttl`` if their backend does not advance
    real time (e.g. ``fakeredis``).
    """

    def _make_cache(self, *, ttl: int = 60) -> Any:
        raise NotImplementedError

    def _advance_past_ttl(self, cache: Any, ttl: int) -> None:
        """Skip past ``ttl`` seconds. Default sleeps just over one TTL."""
        del cache
        time.sleep(ttl + 0.1)

    # ── Scenarios ─────────────────────────────────────────────────────────────

    def test_get_returns_none_on_miss(self) -> None:
        cache = self._make_cache()
        assert cache.get("never-cached") is None

    def test_set_then_get_round_trips(self) -> None:
        cache = self._make_cache()
        principal = _principal()
        cache.set("token-1", principal)
        retrieved = cache.get("token-1")
        assert retrieved is not None
        assert retrieved.user_id == principal.user_id
        assert retrieved.email == principal.email
        assert retrieved.is_active == principal.is_active
        assert retrieved.is_verified == principal.is_verified
        assert retrieved.authz_version == principal.authz_version

    def test_pop_removes_entry(self) -> None:
        cache = self._make_cache()
        cache.set("token-1", _principal())
        cache.pop("token-1")
        assert cache.get("token-1") is None

    def test_pop_missing_token_is_idempotent(self) -> None:
        """Popping a token that was never set MUST NOT raise."""
        cache = self._make_cache()
        cache.pop("never-set")
        # And it must also leave the cache otherwise empty.
        assert cache.get("never-set") is None

    def test_invalidate_user_removes_all_their_entries(self) -> None:
        """``invalidate_user`` MUST evict every token cached for that user.

        The secondary user→token index is what makes this efficient on
        the Redis backend; the contract scenario verifies the *effect*,
        not the index shape, so both backends pass identically.
        """
        cache = self._make_cache()
        user_id = uuid4()
        cache.set("token-a", _principal(user_id=user_id))
        cache.set("token-b", _principal(user_id=user_id))
        # An unrelated user must NOT be touched.
        other_user_id = uuid4()
        cache.set("token-c", _principal(user_id=other_user_id))
        cache.invalidate_user(user_id)
        assert cache.get("token-a") is None
        assert cache.get("token-b") is None
        retained = cache.get("token-c")
        assert retained is not None
        assert retained.user_id == other_user_id

    def test_invalidate_user_with_no_entries_is_a_noop(self) -> None:
        cache = self._make_cache()
        cache.invalidate_user(uuid4())  # MUST NOT raise

    def test_entry_expires_after_ttl(self) -> None:
        """A cached entry MUST stop being returned once its TTL elapses."""
        cache = self._make_cache(ttl=1)
        cache.set("token-ttl", _principal())
        assert cache.get("token-ttl") is not None
        self._advance_past_ttl(cache, ttl=1)
        assert cache.get("token-ttl") is None
