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
        """Persist a new user. Returns ``Err(UserAlreadyExistsError())`` on conflict."""
        ...

    def list_paginated(
        self,
        *,
        cursor: tuple[datetime, UUID] | None = None,
        limit: int = 50,
    ) -> list[User]:
        """Return a page of users ordered by ``(created_at, id)`` ascending.

        Pagination is keyset-based to keep deep pages constant-time and
        stable under concurrent inserts: pass the ``(created_at, id)`` of
        the last row from the previous page as ``cursor`` and the
        implementation will return strictly subsequent rows. A ``None``
        cursor returns the first page.
        """
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

    def set_active_atomically_with(
        self,
        writer: object,
        user_id: UUID,
        *,
        is_active: bool,
    ) -> None:
        """Stage ``set_active`` on the writer's underlying transaction.

        ``writer`` is an :class:`OutboxWriter` produced by
        :meth:`OutboxUnitOfWorkPort.transaction`. SQLModel-aware
        adapters extract the active ``Session`` from the writer (via
        :attr:`SessionSQLModelOutboxAdapter.session`) and stage the
        user-row update on it so the outbox row and the user mutation
        commit or roll back together. Adapters that cannot bind to the
        writer's transaction (e.g. inline-dispatch e2e fakes that have
        no shared session) MAY fall back to :meth:`set_active`; the
        atomic guarantee is then exercised only by the integration
        suite, mirroring the established :class:`OutboxUnitOfWorkPort`
        contract.
        """
        ...

    def update_last_login(self, user_id: UUID, when: datetime) -> None:
        """Stamp ``last_login_at`` and ``updated_at`` to ``when``."""
        ...
