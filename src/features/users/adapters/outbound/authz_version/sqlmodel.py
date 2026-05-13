"""SQLModel implementations of ``UserAuthzVersionPort``.

The principal cache keys on ``(user_id, authz_version)``; incrementing
the column on a user's row invalidates any previously-cached principal
the next time the platform's principal resolver runs.

Two flavours mirror the authorization adapter so a feature's
unit-of-work can commit a resource write, an owner-tuple write, and the
authz-version bump as a single transaction.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.engine import Engine
from sqlmodel import Session

from features.users.adapters.outbound.persistence.sqlmodel.models import (
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
        """Open a fresh session, delegate to ``bump_in_session``, and commit.

        Preserved as a thin wrapper so call sites without a session in
        hand (tests, ad-hoc maintenance scripts) continue to work
        unchanged. The atomic grant/revoke paths go through
        ``bump_in_session`` instead so the bump shares the relationship
        write's transaction.
        """
        with Session(self._engine, expire_on_commit=False) as session:
            try:
                self.bump_in_session(session, user_id)
                session.commit()
            except Exception:
                session.rollback()
                raise

    def bump_in_session(self, session: Session, user_id: UUID) -> None:
        """Stage the bump against ``session`` without committing.

        The caller owns the commit boundary so the bump can land
        atomically with the relationship write it accompanies.
        """
        _bump_one(session, user_id)


class SessionSQLModelUserAuthzVersionAdapter:
    """Adapter that borrows an outer unit-of-work's session.

    Used inside a feature's UoW so the resource write, owner-tuple write,
    and authz-version bump commit or roll back as a single transaction.
    The outer UoW owns commit; this adapter only stages the update.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def bump(self, user_id: UUID) -> None:
        _bump_one(self._session, user_id)

    def bump_in_session(self, session: Session, user_id: UUID) -> None:
        """Stage the bump against ``session`` without committing.

        Satisfies the ``UserAuthzVersionPort`` Protocol so both adapters
        expose the same surface. The session-scoped adapter typically
        receives its own ``self._session`` here, but accepting an
        explicit ``session`` argument keeps the contract uniform with
        the engine-owning adapter.
        """
        _bump_one(session, user_id)
