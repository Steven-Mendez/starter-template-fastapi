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


class UserPublicSelf(BaseModel):
    """Self-view projection of a user row.

    Mirrors :class:`UserPublic` minus internal fields a user should not
    see about themselves. The redacted set is exactly ``{"authz_version"}``
    — an internal cache-invalidation counter whose history would leak
    permission-change events (e.g. a role granted then revoked) to the
    user. Admin views keep :class:`UserPublic` because operators need the
    counter for cache reasoning.
    """

    id: UUID
    email: str
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ErasureAccepted(BaseModel):
    """Response body for ``DELETE /me/erase`` and admin erase endpoints.

    The shape mirrors the 202-Accepted convention: a ``status`` marker,
    the ``job_id`` clients can poll on, and an upper-bound
    ``estimated_completion_seconds`` so the UI can pace a "still
    working" message. The job-status endpoint itself is intentionally
    out of scope for this proposal (see ``design.md`` Non-goals).
    """

    status: str
    job_id: str
    estimated_completion_seconds: int


class ExportResponse(BaseModel):
    """Response body for ``GET /me/export`` and ``GET /admin/users/{id}/export``."""

    download_url: str
    expires_at: datetime


class EraseSelfRequest(BaseModel):
    """Body for ``DELETE /me/erase``.

    Re-auth is required so a stolen access token cannot erase the
    account on its own. Password-less accounts (future SSO-only flows)
    are not in scope for this proposal — see ``EraseUser`` use case
    docstring for the deferred branch.
    """

    password: str


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
