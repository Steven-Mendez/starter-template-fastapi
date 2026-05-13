"""Inbound port: contract the authentication feature uses to reach users."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from app_platform.shared.result import Result
from features.users.application.errors import UserError
from features.users.domain.user import User


class UserPort(Protocol):
    """Read/write contract for the ``User`` entity.

    Implementations live in the users feature. The authentication feature
    depends on this Protocol only and never imports concrete adapters or
    SQLModel tables. The port deals in profile-shaped state only;
    password credentials live in authentication's ``CredentialRepositoryPort``.
    """

    def get_by_id(self, user_id: UUID) -> User | None:
        """Return the user with the given id, or ``None`` if absent."""
        ...

    def get_by_email(self, email: str) -> User | None:
        """Return the user with the given email (case-insensitive), or ``None``."""
        ...

    def create(self, *, email: str) -> Result[User, UserError]:
        """Persist a new user. Returns ``Err(DUPLICATE_EMAIL)`` on conflict."""
        ...

    def list_paginated(self, *, offset: int = 0, limit: int = 50) -> list[User]:
        """Return a page of users ordered by ``created_at`` ascending."""
        ...

    def mark_verified(self, user_id: UUID) -> None:
        """Set ``is_verified=True`` on the user (idempotent)."""
        ...

    def bump_authz_version(self, user_id: UUID) -> None:
        """Increment ``authz_version`` so cached principals are invalidated.

        Called by authentication after a credential change so any access
        token that decoded against the previous version is rejected on
        the next request.
        """
        ...

    def update_email(self, user_id: UUID, new_email: str) -> Result[User, UserError]:
        """Replace the user's email (case-insensitive)."""
        ...

    def set_active(self, user_id: UUID, *, is_active: bool) -> None:
        """Activate or deactivate the user; bumps ``authz_version``."""
        ...

    def update_last_login(self, user_id: UUID, when: datetime) -> None:
        """Stamp ``last_login_at`` and ``updated_at`` to ``when``."""
        ...
