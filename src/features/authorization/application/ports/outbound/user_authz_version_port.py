"""Port for invalidating cached principals after a relationship change.

The principal cache keys on ``(user_id, authz_version)``; bumping the
column on a user's row guarantees the next request rejects any
previously-cached principal. Authorization never touches the ``users``
table directly — it calls this port and lets auth perform the bump.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID


class UserAuthzVersionPort(Protocol):
    """Cache-invalidation seam between authorization and auth."""

    def bump(self, user_id: UUID) -> None:
        """Increment ``users.authz_version`` for ``user_id``.

        SHALL be a no-op if the user does not exist. Implementations
        SHALL bump the column atomically with the surrounding
        transaction so a relationship write + version bump commits or
        rolls back as a unit.
        """
        ...
