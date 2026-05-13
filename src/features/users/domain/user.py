"""User entity owned by the users feature."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _require_aware(value: datetime | None, *, field_name: str) -> None:
    if value is not None and value.tzinfo is None:
        raise ValueError(f"{field_name} must be a timezone-aware datetime")


@dataclass(slots=True)
class User:
    """User account record.

    The ``authz_version`` counter is incremented whenever the user gains
    or loses a relationship tuple. The platform's principal cache keys
    on ``(user_id, authz_version)``, so a bump immediately invalidates
    any cached access-token decode for this user. Password credentials
    live in the authentication feature's ``credentials`` table and are
    not exposed on the user entity.
    """

    id: UUID
    email: str
    is_active: bool = True
    is_verified: bool = False
    authz_version: int = 1
    created_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)
    last_login_at: datetime | None = None

    def __post_init__(self) -> None:
        _require_aware(self.created_at, field_name="User.created_at")
        _require_aware(self.updated_at, field_name="User.updated_at")
        _require_aware(self.last_login_at, field_name="User.last_login_at")
