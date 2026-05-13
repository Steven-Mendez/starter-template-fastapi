"""Port the authorization feature uses to drop cached principals.

The authentication feature maintains the read-through principal cache;
authorization owns the writes that invalidate it. This Protocol is the
seam between the two — authorization never imports the auth-side
``PrincipalCachePort`` directly, mirroring the ``AuditPort`` pattern.

Invalidation is best-effort: the durable correctness signal is the
``authz_version`` column bumped inside the relationship write's
transaction (see ``UserAuthzVersionPort.bump_in_session``). The cache
invalidation is an optimisation that keeps stale entries from being
served for the rest of their TTL window; a Redis blip swallowing the
call does not compromise correctness.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID


class PrincipalCacheInvalidatorPort(Protocol):
    """Best-effort cache-invalidation seam authorization calls on grant/revoke."""

    def invalidate_user(self, user_id: UUID) -> None:
        """Evict every cached principal entry for ``user_id``.

        Implementations MAY raise on transport failures (e.g., Redis
        unavailable). The use-case layer is responsible for catching
        and logging those exceptions so a cache outage never poisons a
        successful authorization grant — the DB-side
        ``authz_version`` bump is the durable correctness signal.
        """
        ...
