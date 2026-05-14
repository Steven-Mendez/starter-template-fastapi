"""In-memory ``UserPort`` implementation for unit tests."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app_platform.shared.result import Err, Ok, Result
from features.users.application.errors import (
    UserAlreadyExistsError,
    UserError,
    UserNotFoundError,
)
from features.users.domain.user import User


def _aware_now() -> datetime:
    return datetime.now(UTC)


@dataclass(slots=True)
class _Stores:
    users: dict[UUID, User] = field(default_factory=dict)
    users_by_email: dict[str, UUID] = field(default_factory=dict)


class FakeUserPort:
    """Dict-backed implementation of ``UserPort`` for unit tests."""

    def __init__(self) -> None:
        self._s = _Stores()

    def reset(self) -> None:
        self._s = _Stores()

    def get_by_id(self, user_id: UUID) -> User | None:
        existing = self._s.users.get(user_id)
        if existing is None or existing.is_erased:
            return None
        return existing

    def get_by_email(self, email: str) -> User | None:
        user_id = self._s.users_by_email.get(email.lower())
        if user_id is None:
            return None
        existing = self._s.users.get(user_id)
        if existing is None or existing.is_erased:
            return None
        return existing

    def create(self, *, email: str) -> Result[User, UserError]:
        normalized = email.lower()
        if normalized in self._s.users_by_email:
            return Err(UserAlreadyExistsError())
        now = _aware_now()
        user = User(
            id=uuid4(),
            email=normalized,
            is_active=True,
            is_verified=False,
            authz_version=1,
            created_at=now,
            updated_at=now,
            last_login_at=None,
        )
        self._s.users[user.id] = user
        self._s.users_by_email[normalized] = user.id
        return Ok(user)

    def list_paginated(
        self,
        *,
        cursor: tuple[datetime, UUID] | None = None,
        limit: int = 50,
    ) -> list[User]:
        ordered = sorted(self._s.users.values(), key=lambda u: (u.created_at, u.id))
        if cursor is not None:
            ordered = [u for u in ordered if (u.created_at, u.id) > cursor]
        return ordered[:limit]

    def mark_verified(self, user_id: UUID) -> None:
        existing = self._s.users.get(user_id)
        if existing is None or existing.is_verified:
            return
        self._s.users[user_id] = replace(
            existing, is_verified=True, updated_at=_aware_now()
        )

    def bump_authz_version(self, user_id: UUID) -> None:
        existing = self._s.users.get(user_id)
        if existing is None:
            return
        self._s.users[user_id] = replace(
            existing,
            authz_version=existing.authz_version + 1,
            updated_at=_aware_now(),
        )

    def update_email(self, user_id: UUID, new_email: str) -> Result[User, UserError]:
        existing = self._s.users.get(user_id)
        if existing is None:
            return Err(UserNotFoundError())
        normalized = new_email.lower()
        if (
            normalized in self._s.users_by_email
            and self._s.users_by_email[normalized] != user_id
        ):
            return Err(UserAlreadyExistsError())
        del self._s.users_by_email[existing.email]
        updated = replace(existing, email=normalized, updated_at=_aware_now())
        self._s.users[user_id] = updated
        self._s.users_by_email[normalized] = user_id
        return Ok(updated)

    def set_active(self, user_id: UUID, *, is_active: bool) -> None:
        existing = self._s.users.get(user_id)
        if existing is None:
            return
        self._s.users[user_id] = replace(
            existing,
            is_active=is_active,
            authz_version=existing.authz_version + 1,
            updated_at=_aware_now(),
        )

    def set_active_atomically_with(
        self,
        writer: object,
        user_id: UUID,
        *,
        is_active: bool,
    ) -> None:
        # Fake has no real transaction; just delegate. Tests that need
        # to observe the inline-write-into-writer behavior assert on
        # the writer's enqueued rows directly.
        _ = writer
        self.set_active(user_id, is_active=is_active)

    def update_last_login(self, user_id: UUID, when: datetime) -> None:
        existing = self._s.users.get(user_id)
        if existing is None:
            return
        self._s.users[user_id] = replace(existing, last_login_at=when, updated_at=when)

    def get_raw_by_id(self, user_id: UUID) -> User | None:
        return self._s.users.get(user_id)

    def scrub_for_erasure_atomically_with(
        self,
        writer: object,
        user_id: UUID,
    ) -> bool:
        _ = writer  # fake has no real transaction
        existing = self._s.users.get(user_id)
        if existing is None or existing.is_erased:
            return False
        scrubbed = replace(
            existing,
            email=f"erased+{existing.id}@erased.invalid",
            is_active=False,
            is_erased=True,
            last_login_at=None,
            authz_version=existing.authz_version + 1,
            updated_at=_aware_now(),
        )
        # Free the original email so a fresh registration can claim it.
        if existing.email in self._s.users_by_email:
            del self._s.users_by_email[existing.email]
        self._s.users[user_id] = scrubbed
        self._s.users_by_email[scrubbed.email] = user_id
        return True

    @property
    def stored_users(self) -> dict[UUID, User]:
        return self._s.users
