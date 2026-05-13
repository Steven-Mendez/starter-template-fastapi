"""Port for invalidating cached principals after a relationship change.

The principal cache keys on ``(user_id, authz_version)``; bumping the
column on a user's row guarantees the next request rejects any
previously-cached principal. Authorization never touches the ``users``
table directly — it calls this port and lets auth perform the bump.
"""

from __future__ import annotations

from typing import Any, Protocol
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

    def bump_in_session(self, session: Any, user_id: UUID) -> None:
        """Increment ``users.authz_version`` for ``user_id`` using ``session``.

        Performs the version increment against the supplied session
        without committing. The caller owns the commit boundary so the
        bump can land atomically with the relationship write it
        accompanies. SHALL be a no-op if the user does not exist.

        ``session`` is typed as :class:`Any` so this port can stay free
        of the SQLModel/SQLAlchemy types that live in the adapter layer
        (the application layer must not import from ``sqlmodel`` or
        ``sqlalchemy``; that boundary is enforced by Import Linter).
        """
        ...
