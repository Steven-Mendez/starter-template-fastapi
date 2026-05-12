"""SQLModel-backed :class:`UserPort` implementation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from src.features.users.adapters.outbound.persistence.sqlmodel.models import (
    UserTable,
    utc_now,
)
from src.features.users.application.errors import UserError
from src.features.users.domain.user import User
from src.platform.shared.result import Err, Ok, Result


def _ensure_utc(value: datetime | None) -> datetime | None:
    """Coerce naive timestamps to UTC at the persistence boundary.

    SQLite-backed test fixtures drop tzinfo on round-trip even though the
    column is declared ``DateTime(timezone=True)``. Coercing once here
    lets the domain validators reject naive datetimes everywhere else.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _to_domain(row: UserTable) -> User:
    created = _ensure_utc(row.created_at) or datetime.now(timezone.utc)
    updated = _ensure_utc(row.updated_at) or datetime.now(timezone.utc)
    return User(
        id=row.id,
        email=row.email,
        is_active=row.is_active,
        is_verified=row.is_verified,
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
            return _to_domain(row) if row else None

    def get_by_email(self, email: str) -> User | None:
        with Session(self.engine) as session:
            stmt = select(UserTable).where(UserTable.email == email.lower())
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
                return Err(UserError.DUPLICATE_EMAIL)
            session.refresh(row)
            return Ok(_to_domain(row))

    def list_paginated(self, *, offset: int = 0, limit: int = 50) -> list[User]:
        with Session(self.engine) as session:
            stmt = (
                select(UserTable)
                .order_by(UserTable.created_at)  # type: ignore[arg-type]
                .offset(offset)
                .limit(limit)
            )
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
                return Err(UserError.NOT_FOUND)
            row.email = normalized
            row.updated_at = utc_now()
            session.add(row)
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                return Err(UserError.DUPLICATE_EMAIL)
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

    def update_last_login(self, user_id: UUID, when: datetime) -> None:
        with Session(self.engine, expire_on_commit=False) as session:
            row = session.get(UserTable, user_id)
            if row is None:
                return
            row.last_login_at = when
            row.updated_at = when
            session.add(row)
            session.commit()


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
        return _to_domain(row) if row else None

    def get_by_email(self, email: str) -> User | None:
        stmt = select(UserTable).where(UserTable.email == email.lower())
        row = self.session.exec(stmt).first()
        return _to_domain(row) if row else None

    def create(self, *, email: str) -> Result[User, UserError]:
        row = UserTable(email=email.lower())
        self.session.add(row)
        try:
            self.session.flush()
        except IntegrityError:
            return Err(UserError.DUPLICATE_EMAIL)
        return Ok(_to_domain(row))

    def list_paginated(self, *, offset: int = 0, limit: int = 50) -> list[User]:
        stmt = (
            select(UserTable)
            .order_by(UserTable.created_at)  # type: ignore[arg-type]
            .offset(offset)
            .limit(limit)
        )
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
            return Err(UserError.NOT_FOUND)
        row.email = normalized
        row.updated_at = utc_now()
        self.session.add(row)
        try:
            self.session.flush()
        except IntegrityError:
            return Err(UserError.DUPLICATE_EMAIL)
        return Ok(_to_domain(row))

    def set_active(self, user_id: UUID, *, is_active: bool) -> None:
        row = self.session.get(UserTable, user_id)
        if row is None:
            return
        row.is_active = is_active
        row.authz_version += 1
        row.updated_at = utc_now()
        self.session.add(row)

    def update_last_login(self, user_id: UUID, when: datetime) -> None:
        row = self.session.get(UserTable, user_id)
        if row is None:
            return
        row.last_login_at = when
        row.updated_at = when
        self.session.add(row)
