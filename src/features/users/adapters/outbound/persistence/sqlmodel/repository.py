"""SQLModel-backed :class:`UserPort` implementation."""

from __future__ import annotations

from dataclasses import dataclass
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


def _to_domain(row: UserTable) -> User:
    return User(
        id=row.id,
        email=row.email,
        password_hash=row.password_hash,
        is_active=row.is_active,
        is_verified=row.is_verified,
        authz_version=row.authz_version,
        created_at=row.created_at,
        updated_at=row.updated_at,
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

    def create(
        self,
        *,
        email: str,
        password_hash: str,
    ) -> Result[User, UserError]:
        with Session(self.engine, expire_on_commit=False) as session:
            row = UserTable(email=email.lower(), password_hash=password_hash)
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

    def update_password_hash(self, user_id: UUID, new_hash: str) -> None:
        with Session(self.engine, expire_on_commit=False) as session:
            row = session.get(UserTable, user_id)
            if row is None:
                raise KeyError(f"User {user_id} does not exist")
            row.password_hash = new_hash
            row.updated_at = utc_now()
            session.add(row)
            session.commit()
