"""Pydantic schemas for the users HTTP endpoints."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class UserPublic(BaseModel):
    """Public projection of a user row."""

    id: UUID
    email: str
    is_active: bool
    is_verified: bool
    authz_version: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserListPage(BaseModel):
    """Keyset-paginated page of users for ``GET /admin/users``.

    ``next_cursor`` is a base64-encoded ``(created_at, id)`` tuple — pass
    it back as ``?cursor=...`` to fetch the next page. ``next_cursor`` is
    ``None`` when no further rows exist.
    """

    items: list[UserPublic]
    count: int
    limit: int
    next_cursor: str | None = None


class UpdateProfileRequest(BaseModel):
    """Body for ``PATCH /me``."""

    email: str | None = None
