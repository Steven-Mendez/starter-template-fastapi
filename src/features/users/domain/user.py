"""User entity owned by the users feature."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class User:
    """User account record.

    The ``authz_version`` counter is incremented whenever the user gains
    or loses a relationship tuple. The platform's principal cache keys
    on ``(user_id, authz_version)``, so a bump immediately invalidates
    any cached access-token decode for this user.

    ``password_hash`` is exposed here for backwards compatibility during
    the credentials-split migration; it will move to the authentication
    feature's ``credentials`` table and be removed from this dataclass
    in a follow-up.
    """

    id: UUID
    email: str
    password_hash: str
    is_active: bool = True
    is_verified: bool = False
    authz_version: int = 1
    created_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)
