"""SQLModel-backed :class:`UserPort` implementation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app_platform.shared.result import Err, Ok, Result
from features.users.adapters.outbound.persistence.sqlmodel.models import (
    UserTable,
    utc_now,
)
from features.users.application.errors import (
    UserAlreadyExistsError,
    UserError,
    UserNotFoundError,
)
from features.users.domain.user import User


def _ensure_utc(value: datetime | None) -> datetime | None:
    """Coerce naive timestamps to UTC at the persistence boundary.

    SQLite-backed test fixtures drop tzinfo on round-trip even though the
    column is declared ``DateTime(timezone=True)``. Coercing once here
    lets the domain validators reject naive datetimes everywhere else.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _to_domain(row: UserTable) -> User:
    created = _ensure_utc(row.created_at) or datetime.now(UTC)
    updated = _ensure_utc(row.updated_at) or datetime.now(UTC)
    return User(
        id=row.id,
        email=row.email,
        is_active=row.is_active,
        is_verified=row.is_verified,
        is_erased=row.is_erased,
        authz_version=row.authz_version,
        created_at=created,
        updated_at=updated,
        last_login_at=_ensure_utc(row.last_login_at),
    )


@dataclass(slots=True)
class SQLModelUserRepository:
    """Engine-owning :class:`UserPort` implementation."""

    engine: Engine

    def get_by_id(self, user_id: UUID) -> User | None:
        with Session(self.engine) as session:
            row = session.get(UserTable, user_id)
            # Erased users are invisible to readers (GDPR Art. 17). The
            # row itself survives so audit trail and FKs stay consistent,
            # but ``UserPort`` callers see ``None`` — every cached
            # principal entry therefore resolves to "user not found"
            # within the principal cache TTL.
            if row is None or row.is_erased:
                return None
            return _to_domain(row)

    def get_by_email(self, email: str) -> User | None:
        with Session(self.engine) as session:
            stmt = select(UserTable).where(
                UserTable.email == email.lower(),
                UserTable.is_erased == False,  # noqa: E712 — SQL boolean comparison
            )
            row = session.exec(stmt).first()
            return _to_domain(row) if row else None

    def create(self, *, email: str) -> Result[User, UserError]:
        with Session(self.engine, expire_on_commit=False) as session:
            row = UserTable(email=email.lower())
            session.add(row)
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                return Err(UserAlreadyExistsError())
            session.refresh(row)
            return Ok(_to_domain(row))

    def list_paginated(
        self,
        *,
        cursor: tuple[datetime, UUID] | None = None,
        limit: int = 50,
    ) -> list[User]:
        with Session(self.engine) as session:
            stmt = select(UserTable).order_by(
                UserTable.created_at,  # type: ignore[arg-type]
                UserTable.id,  # type: ignore[arg-type]
            )
            if cursor is not None:
                created_at, last_id = cursor
                stmt = stmt.where(
                    sa.tuple_(cast(Any, UserTable.created_at), cast(Any, UserTable.id))
                    > sa.tuple_(sa.literal(created_at), sa.literal(last_id))
                )
            stmt = stmt.limit(limit)
            return [_to_domain(r) for r in session.exec(stmt).all()]

    def mark_verified(self, user_id: UUID) -> None:
        with Session(self.engine, expire_on_commit=False) as session:
            row = session.get(UserTable, user_id)
            if row is None or row.is_verified:
                return
            row.is_verified = True
            row.updated_at = utc_now()
            session.add(row)
            session.commit()

    def bump_authz_version(self, user_id: UUID) -> None:
        with Session(self.engine, expire_on_commit=False) as session:
            row = session.get(UserTable, user_id)
            if row is None:
                return
            row.authz_version += 1
            row.updated_at = utc_now()
            session.add(row)
            session.commit()

    def update_email(self, user_id: UUID, new_email: str) -> Result[User, UserError]:
        normalized = new_email.strip().lower()
        with Session(self.engine, expire_on_commit=False) as session:
            row = session.get(UserTable, user_id)
            if row is None:
                return Err(UserNotFoundError())
            row.email = normalized
            row.updated_at = utc_now()
            session.add(row)
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                return Err(UserAlreadyExistsError())
            session.refresh(row)
            return Ok(_to_domain(row))

    def set_active(self, user_id: UUID, *, is_active: bool) -> None:
        with Session(self.engine, expire_on_commit=False) as session:
            row = session.get(UserTable, user_id)
            if row is None:
                return
            row.is_active = is_active
            row.authz_version += 1
            row.updated_at = utc_now()
            session.add(row)
            session.commit()

    def set_active_atomically_with(
        self,
        writer: object,
        user_id: UUID,
        *,
        is_active: bool,
    ) -> None:
        """Stage ``set_active`` on the writer's transaction when possible.

        Mirrors the auth feature's :class:`_SessionIssueTokenTransaction`
        pattern: if the writer exposes a SQLModel ``Session``, the
        user row update is staged on it so the outer outbox commit
        covers both writes. Writers without a shared session (inline-
        dispatch e2e fakes) fall back to the engine-owning
        :meth:`set_active`; integration tests cover the atomic path
        against a real PostgreSQL.
        """
        session = getattr(writer, "session", None)
        if isinstance(session, Session):
            row = session.get(UserTable, user_id)
            if row is None:
                return
            row.is_active = is_active
            row.authz_version += 1
            row.updated_at = utc_now()
            session.add(row)
            return
        # Fallback: writer is not session-backed (e.g. inline-dispatch
        # e2e fake). The user row commits in its own transaction.
        self.set_active(user_id, is_active=is_active)

    def update_last_login(self, user_id: UUID, when: datetime) -> None:
        with Session(self.engine, expire_on_commit=False) as session:
            row = session.get(UserTable, user_id)
            if row is None:
                return
            row.last_login_at = when
            row.updated_at = when
            session.add(row)
            session.commit()

    def get_raw_by_id(self, user_id: UUID) -> User | None:
        """Read a user row even if it is erased.

        ``get_by_id`` filters out erased rows so cached principals
        dissolve; the erasure use case needs to detect "already erased"
        state for idempotency and the export endpoint similarly needs
        the surviving row. The raw read SHOULD NOT be exposed beyond
        the lifecycle use cases that own the erasure pipeline.
        """
        with Session(self.engine) as session:
            row = session.get(UserTable, user_id)
            return _to_domain(row) if row else None

    def scrub_for_erasure_atomically_with(
        self,
        writer: object,
        user_id: UUID,
    ) -> bool:
        """Stage the GDPR-Art.17 user-row scrub on ``writer``'s transaction.

        Returns ``True`` if the row was scrubbed by this call, ``False``
        if the row was missing or already erased (idempotent re-runs).

        Email is replaced with a stable ``erased+{user_id}@erased.invalid``
        placeholder so the unique-on-email index stays trivially
        satisfied; ``last_login_at`` is nulled; ``authz_version`` is
        bumped so every cached principal entry resolves to "user not
        found" within the cache TTL; ``is_verified`` is preserved (a
        non-PII state fact).

        Falls back to the engine-owning :meth:`_scrub_for_erasure` when
        the writer is not session-backed (inline-dispatch e2e fakes);
        the atomic guarantee is then exercised only by the integration
        suite, mirroring :meth:`set_active_atomically_with`.
        """
        session = getattr(writer, "session", None)
        if isinstance(session, Session):
            row = session.get(UserTable, user_id)
            if row is None or row.is_erased:
                return False
            _apply_erasure_scrub(row)
            session.add(row)
            return True
        return self._scrub_for_erasure(user_id)

    def _scrub_for_erasure(self, user_id: UUID) -> bool:
        with Session(self.engine, expire_on_commit=False) as session:
            row = session.get(UserTable, user_id)
            if row is None or row.is_erased:
                return False
            _apply_erasure_scrub(row)
            session.add(row)
            session.commit()
            return True


def _apply_erasure_scrub(row: UserTable) -> None:
    """Mutate ``row`` in place to its post-erasure shape.

    Shared between the engine-owning and the writer-bound code paths so
    the two stay in lock-step. The scrub list grows alongside the PII
    inventory in ``docs/operations.md`` — every new user-adjacent
    column must be addressed here.
    """
    row.email = f"erased+{row.id}@erased.invalid"
    row.is_active = False
    row.is_erased = True
    row.last_login_at = None
    row.authz_version += 1
    row.updated_at = utc_now()


@dataclass(slots=True)
class SessionSQLModelUserRepository:
    """Session-bound :class:`UserPort` implementation.

    Used inside an outer feature's unit of work so the user write commits
    or rolls back with the rest of the transaction. The outer UoW owns
    commit; this adapter only stages updates.
    """

    session: Session

    def get_by_id(self, user_id: UUID) -> User | None:
        row = self.session.get(UserTable, user_id)
        if row is None or row.is_erased:
            return None
        return _to_domain(row)

    def get_by_email(self, email: str) -> User | None:
        stmt = select(UserTable).where(
            UserTable.email == email.lower(),
            UserTable.is_erased == False,  # noqa: E712 — SQL boolean comparison
        )
        row = self.session.exec(stmt).first()
        return _to_domain(row) if row else None

    def create(self, *, email: str) -> Result[User, UserError]:
        row = UserTable(email=email.lower())
        self.session.add(row)
        try:
            self.session.flush()
        except IntegrityError:
            return Err(UserAlreadyExistsError())
        return Ok(_to_domain(row))

    def list_paginated(
        self,
        *,
        cursor: tuple[datetime, UUID] | None = None,
        limit: int = 50,
    ) -> list[User]:
        stmt = select(UserTable).order_by(
            UserTable.created_at,  # type: ignore[arg-type]
            UserTable.id,  # type: ignore[arg-type]
        )
        if cursor is not None:
            created_at, last_id = cursor
            stmt = stmt.where(
                sa.tuple_(cast(Any, UserTable.created_at), cast(Any, UserTable.id))
                > sa.tuple_(sa.literal(created_at), sa.literal(last_id))
            )
        stmt = stmt.limit(limit)
        return [_to_domain(r) for r in self.session.exec(stmt).all()]

    def mark_verified(self, user_id: UUID) -> None:
        row = self.session.get(UserTable, user_id)
        if row is None or row.is_verified:
            return
        row.is_verified = True
        row.updated_at = utc_now()
        self.session.add(row)

    def bump_authz_version(self, user_id: UUID) -> None:
        row = self.session.get(UserTable, user_id)
        if row is None:
            return
        row.authz_version += 1
        row.updated_at = utc_now()
        self.session.add(row)

    def update_email(self, user_id: UUID, new_email: str) -> Result[User, UserError]:
        normalized = new_email.strip().lower()
        row = self.session.get(UserTable, user_id)
        if row is None:
            return Err(UserNotFoundError())
        row.email = normalized
        row.updated_at = utc_now()
        self.session.add(row)
        try:
            self.session.flush()
        except IntegrityError:
            return Err(UserAlreadyExistsError())
        return Ok(_to_domain(row))

    def set_active(self, user_id: UUID, *, is_active: bool) -> None:
        row = self.session.get(UserTable, user_id)
        if row is None:
            return
        row.is_active = is_active
        row.authz_version += 1
        row.updated_at = utc_now()
        self.session.add(row)

    def set_active_atomically_with(
        self,
        writer: object,
        user_id: UUID,
        *,
        is_active: bool,
    ) -> None:
        """Session-scoped variant: stage the write on the writer's session.

        Falls back to the session-bound :meth:`set_active` when the
        writer does not expose a SQLModel session.
        """
        session = getattr(writer, "session", None)
        if isinstance(session, Session):
            row = session.get(UserTable, user_id)
            if row is None:
                return
            row.is_active = is_active
            row.authz_version += 1
            row.updated_at = utc_now()
            session.add(row)
            return
        self.set_active(user_id, is_active=is_active)

    def update_last_login(self, user_id: UUID, when: datetime) -> None:
        row = self.session.get(UserTable, user_id)
        if row is None:
            return
        row.last_login_at = when
        row.updated_at = when
        self.session.add(row)

    def get_raw_by_id(self, user_id: UUID) -> User | None:
        row = self.session.get(UserTable, user_id)
        return _to_domain(row) if row else None

    def scrub_for_erasure_atomically_with(
        self,
        writer: object,
        user_id: UUID,
    ) -> bool:
        session = getattr(writer, "session", None)
        if isinstance(session, Session):
            row = session.get(UserTable, user_id)
            if row is None or row.is_erased:
                return False
            _apply_erasure_scrub(row)
            session.add(row)
            return True
        # Session-bound adapter without a writer-session fallback: stage
        # on the bound session.
        row = self.session.get(UserTable, user_id)
        if row is None or row.is_erased:
            return False
        _apply_erasure_scrub(row)
        self.session.add(row)
        return True
