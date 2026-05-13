"""Adapter wrapping the principal cache for the authorization feature.

Implements :class:`PrincipalCacheInvalidatorPort` by delegating to the
existing :class:`PrincipalCachePort` instance the auth container builds
(in-process or Redis-backed, depending on ``APP_AUTH_REDIS_URL``).

The authorization feature only needs ``invalidate_user``; this adapter
exposes that single method so authorization never depends on the auth
feature's full cache surface — mirroring the ``SQLModelAuditAdapter``
pattern.
"""

from __future__ import annotations

from uuid import UUID

from features.authentication.application.cache import PrincipalCachePort


class PrincipalCacheInvalidatorAdapter:
    """Thin facade that exposes only ``invalidate_user`` to authorization."""

    def __init__(self, cache: PrincipalCachePort) -> None:
        self._cache = cache

    def invalidate_user(self, user_id: UUID) -> None:
        """Forward to the wrapped cache's ``invalidate_user`` method."""
        self._cache.invalidate_user(user_id)
