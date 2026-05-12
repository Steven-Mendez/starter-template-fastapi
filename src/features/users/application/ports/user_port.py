"""Inbound port: contract the authentication feature uses to reach users."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from src.features.users.application.errors import UserError
from src.features.users.domain.user import User
from src.platform.shared.result import Result


class UserPort(Protocol):
    """Read/write contract for the ``User`` entity.

    Implementations live in the users feature. The authentication feature
    depends on this Protocol only and never imports concrete adapters or
    SQLModel tables.
    """

    def get_by_id(self, user_id: UUID) -> User | None:
        """Return the user with the given id, or ``None`` if absent."""
        ...

    def get_by_email(self, email: str) -> User | None:
        """Return the user with the given email (case-insensitive), or ``None``."""
        ...

    def create(
        self,
        *,
        email: str,
        password_hash: str,
    ) -> Result[User, UserError]:
        """Persist a new user. Returns ``Err(DUPLICATE_EMAIL)`` on conflict."""
        ...

    def list_paginated(self, *, offset: int = 0, limit: int = 50) -> list[User]:
        """Return a page of users ordered by ``created_at`` ascending."""
        ...

    def mark_verified(self, user_id: UUID) -> None:
        """Set ``is_verified=True`` on the user (idempotent)."""
        ...

    def update_password_hash(self, user_id: UUID, new_hash: str) -> None:
        """Replace the user's password hash."""
        ...
