"""Unit tests for the auth-side UserAuthzVersionPort adapters."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, create_engine

from src.features.authentication.adapters.outbound.authz_version import (
    SessionSQLModelUserAuthzVersionAdapter,
    SQLModelUserAuthzVersionAdapter,
)
from src.features.authentication.adapters.outbound.persistence.sqlmodel.models import (
    UserTable,
    utc_now,
)

pytestmark = pytest.mark.unit

_SCHEMA: list[Any] = [UserTable]


@pytest.fixture
def engine() -> Iterator[Engine]:
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    for table in _SCHEMA:
        table.__table__.create(eng, checkfirst=True)
    yield eng
    eng.dispose()


def _seed_user(engine: Engine) -> UUID:
    user = UserTable(
        id=uuid4(),
        email=f"user-{uuid4()}@example.com",
        password_hash="x",
        is_active=True,
        is_verified=True,
        authz_version=1,
        created_at=utc_now(),
        updated_at=utc_now(),
        last_login_at=None,
    )
    with Session(engine) as session:
        session.add(user)
        session.commit()
        session.refresh(user)
    return user.id


def _authz_version(engine: Engine, user_id: UUID) -> int:
    with Session(engine) as session:
        row = session.get(UserTable, user_id)
        assert row is not None
        return row.authz_version


def test_bump_increments_authz_version_by_one(engine: Engine) -> None:
    user_id = _seed_user(engine)
    SQLModelUserAuthzVersionAdapter(engine).bump(user_id)
    assert _authz_version(engine, user_id) == 2


def test_bump_is_idempotent_per_call(engine: Engine) -> None:
    user_id = _seed_user(engine)
    adapter = SQLModelUserAuthzVersionAdapter(engine)
    adapter.bump(user_id)
    adapter.bump(user_id)
    adapter.bump(user_id)
    assert _authz_version(engine, user_id) == 4


def test_bump_for_missing_user_is_silent(engine: Engine) -> None:
    SQLModelUserAuthzVersionAdapter(engine).bump(uuid4())


def test_session_scoped_adapter_shares_outer_transaction(engine: Engine) -> None:
    """The session-scoped variant stages the update without committing."""
    user_id = _seed_user(engine)
    with Session(engine, expire_on_commit=False) as session:
        SessionSQLModelUserAuthzVersionAdapter(session).bump(user_id)
        # Not yet committed; the outer session owns lifecycle.
        session.commit()
    assert _authz_version(engine, user_id) == 2


def test_session_scoped_rolls_back_on_outer_failure(engine: Engine) -> None:
    """If the outer transaction rolls back, the bump rolls back too."""
    user_id = _seed_user(engine)
    with Session(engine, expire_on_commit=False) as session:
        SessionSQLModelUserAuthzVersionAdapter(session).bump(user_id)
        session.rollback()
    assert _authz_version(engine, user_id) == 1
