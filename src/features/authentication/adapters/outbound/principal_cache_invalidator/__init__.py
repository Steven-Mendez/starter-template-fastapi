"""Auth-side adapter for the authorization feature's PrincipalCacheInvalidatorPort."""

from __future__ import annotations

from features.authentication.adapters.outbound.principal_cache_invalidator.cache import (  # noqa: E501
    PrincipalCacheInvalidatorAdapter,
)

__all__ = ["PrincipalCacheInvalidatorAdapter"]
