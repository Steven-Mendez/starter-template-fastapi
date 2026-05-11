"""SQLModel implementations of ``UserAuthzVersionPort``.

The principal cache keys on ``(user_id, authz_version)``; incrementing
the column on a user's row invalidates any previously-cached principal
the next time the platform's principal resolver runs.

Two flavours mirror the authorization adapter so the kanban
unit-of-work can commit a board write, an owner-tuple write, and the
authz-version bump as a single transaction.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.engine import Engine
from sqlmodel import Session

from src.features.auth.adapters.outbound.persistence.sqlmodel.models import (
    UserTable,
    utc_now,
)


def _bump_one(session: Session, user_id: UUID) -> None:
    """Increment ``authz_version`` on the row, if it exists.

    A missing user is intentionally silent: a relationship may reference
    a user that no longer exists (e.g., a soft-delete cascade in a
    future schema) and the cache invalidation has nothing to do.
    """
    user = session.get(UserTable, user_id)
    if user is None:
        return
    user.authz_version += 1
    user.updated_at = utc_now()
    session.add(user)


class SQLModelUserAuthzVersionAdapter:
    """Adapter that opens its own short-lived session per bump."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def bump(self, user_id: UUID) -> None:
        with Session(self._engine, expire_on_commit=False) as session:
            try:
                _bump_one(session, user_id)
                session.commit()
            except Exception:
                session.rollback()
                raise


class SessionSQLModelUserAuthzVersionAdapter:
    """Adapter that borrows an outer unit-of-work's session.

    Used inside kanban's UoW so the board write, owner-tuple write, and
    authz-version bump commit or roll back as a single transaction. The
    outer UoW owns commit; this adapter only stages the update.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def bump(self, user_id: UUID) -> None:
        _bump_one(self._session, user_id)
