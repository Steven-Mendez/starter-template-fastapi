"""Pure domain models for the authentication feature.

These dataclasses carry no framework dependencies. They are the
canonical in-memory representation that the application layer works
with; the persistence adapter maps to and from these types at the
boundary. The ``User`` entity lives in the users feature
(``src.features.users.domain.user``).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID


def _require_aware(value: datetime | None, *, field: str) -> None:
    if value is not None and value.tzinfo is None:
        raise ValueError(f"{field} must be a timezone-aware datetime")


@dataclass(frozen=True, slots=True)
class Credential:
    """A persisted credential — today only password hashes; passkey or
    OAuth-link rows can join later by carrying a different ``algorithm``.
    """

    id: UUID
    user_id: UUID
    algorithm: str
    hash: str
    last_changed_at: datetime
    created_at: datetime

    def __post_init__(self) -> None:
        _require_aware(self.last_changed_at, field="Credential.last_changed_at")
        _require_aware(self.created_at, field="Credential.created_at")


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
