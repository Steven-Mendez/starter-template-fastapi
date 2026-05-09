"""Pure domain models for the auth feature.

These dataclasses carry no framework dependencies — no SQLModel, no FastAPI,
no Pydantic. They are the canonical in-memory representation that the
application layer works with; the persistence adapter maps to and from
these types at the boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


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


@dataclass(frozen=True, slots=True)
class Role:
    id: UUID
    name: str
    description: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class Permission:
    id: UUID
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime


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
