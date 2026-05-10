"""Pure domain models for the auth feature.

These dataclasses carry no framework dependencies — no SQLModel, no FastAPI,
no Pydantic. They are the canonical in-memory representation that the
application layer works with; the persistence adapter maps to and from
these types at the boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID


def _require_aware(value: datetime | None, *, field: str) -> None:
    """Raise ``ValueError`` if ``value`` is a naive (tzinfo-less) datetime.

    Domain construction is the canonical entry point for new aggregates;
    enforcing tz-awareness here surfaces accidental ``datetime.utcnow()``
    or string-parsing bugs before they reach the persistence boundary
    where comparisons against aware values would silently fail.
    """
    if value is not None and value.tzinfo is None:
        raise ValueError(f"{field} must be a timezone-aware datetime")


@dataclass(frozen=True, slots=True)
class User:
    id: UUID
    email: str
    password_hash: str
    is_active: bool
    is_verified: bool
    authz_version: int
    created_at: datetime
    updated_at: datetime
    last_login_at: datetime | None

    def __post_init__(self) -> None:
        _require_aware(self.created_at, field="User.created_at")
        _require_aware(self.updated_at, field="User.updated_at")
        _require_aware(self.last_login_at, field="User.last_login_at")


@dataclass(frozen=True, slots=True)
class RefreshToken:
    id: UUID
    user_id: UUID
    token_hash: str
    family_id: UUID
    expires_at: datetime
    revoked_at: datetime | None
    replaced_by_token_id: UUID | None
    created_at: datetime
    created_ip: str | None
    user_agent: str | None

    def __post_init__(self) -> None:
        _require_aware(self.expires_at, field="RefreshToken.expires_at")
        _require_aware(self.revoked_at, field="RefreshToken.revoked_at")
        _require_aware(self.created_at, field="RefreshToken.created_at")


@dataclass(frozen=True, slots=True)
class InternalToken:
    id: UUID
    user_id: UUID | None
    purpose: str
    token_hash: str
    expires_at: datetime
    used_at: datetime | None
    created_at: datetime
    created_ip: str | None

    def __post_init__(self) -> None:
        _require_aware(self.expires_at, field="InternalToken.expires_at")
        _require_aware(self.used_at, field="InternalToken.used_at")
        _require_aware(self.created_at, field="InternalToken.created_at")


@dataclass(frozen=True, slots=True)
class AuditEvent:
    id: UUID
    user_id: UUID | None
    event_type: str
    metadata: dict[str, Any]
    created_at: datetime
    ip_address: str | None
    user_agent: str | None

    def __post_init__(self) -> None:
        _require_aware(self.created_at, field="AuditEvent.created_at")
