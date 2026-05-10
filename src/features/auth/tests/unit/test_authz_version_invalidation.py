"""Unit tests asserting relationship writes bump ``User.authz_version``.

The principal cache keys on ``(user_id, authz_version)``; bumping the
version on every relationship change is what guarantees that a cached
principal is rejected on the next request after the change.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, create_engine

from src.features.auth.adapters.outbound.authorization.sqlmodel import (
    SQLModelAuthorizationAdapter,
)
from src.features.auth.adapters.outbound.persistence.sqlmodel.models import (
    RelationshipTable,
    UserTable,
    utc_now,
)
from src.features.auth.application.authorization.types import Relationship

_SCHEMA: list[Any] = [UserTable, RelationshipTable]

pytestmark = pytest.mark.unit


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


@pytest.fixture
def adapter(engine: Engine) -> SQLModelAuthorizationAdapter:
    return SQLModelAuthorizationAdapter(engine)


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


def test_write_bumps_authz_version_for_user_subject(
    engine: Engine, adapter: SQLModelAuthorizationAdapter
) -> None:
    user_id = _seed_user(engine)
    before = _authz_version(engine, user_id)

    adapter.write_relationships(
        [
            Relationship(
                resource_type="kanban",
                resource_id=str(uuid4()),
                relation="reader",
                subject_type="user",
                subject_id=str(user_id),
            )
        ]
    )

    assert _authz_version(engine, user_id) == before + 1


def test_delete_bumps_authz_version_for_user_subject(
    engine: Engine, adapter: SQLModelAuthorizationAdapter
) -> None:
    user_id = _seed_user(engine)
    tup = Relationship(
        resource_type="kanban",
        resource_id=str(uuid4()),
        relation="reader",
        subject_type="user",
        subject_id=str(user_id),
    )
    adapter.write_relationships([tup])
    after_write = _authz_version(engine, user_id)

    adapter.delete_relationships([tup])

    assert _authz_version(engine, user_id) == after_write + 1


def test_writes_for_multiple_users_bump_each_independently(
    engine: Engine, adapter: SQLModelAuthorizationAdapter
) -> None:
    a = _seed_user(engine)
    b = _seed_user(engine)
    board = str(uuid4())
    adapter.write_relationships(
        [
            Relationship(
                resource_type="kanban",
                resource_id=board,
                relation="reader",
                subject_type="user",
                subject_id=str(a),
            ),
            Relationship(
                resource_type="kanban",
                resource_id=board,
                relation="writer",
                subject_type="user",
                subject_id=str(b),
            ),
        ]
    )
    assert _authz_version(engine, a) == 2
    assert _authz_version(engine, b) == 2


def test_no_bump_for_non_user_subjects(
    engine: Engine, adapter: SQLModelAuthorizationAdapter
) -> None:
    """Future non-user subjects (e.g., service accounts) SHALL NOT touch
    user authz_version; the user table remains the per-user revocation seam."""
    user_id = _seed_user(engine)
    before = _authz_version(engine, user_id)

    adapter.write_relationships(
        [
            Relationship(
                resource_type="kanban",
                resource_id=str(uuid4()),
                relation="reader",
                subject_type="service",
                subject_id="some-service-id",
            )
        ]
    )

    assert _authz_version(engine, user_id) == before


def test_writing_to_a_missing_user_silently_skips_the_bump(
    engine: Engine, adapter: SQLModelAuthorizationAdapter
) -> None:
    """The relationship still persists; only the user-row update is skipped."""
    missing_user_id = str(uuid4())
    adapter.write_relationships(
        [
            Relationship(
                resource_type="kanban",
                resource_id=str(uuid4()),
                relation="reader",
                subject_type="user",
                subject_id=missing_user_id,
            )
        ]
    )
    # No exception raised; the relationship row exists.
    from sqlalchemy import text  # noqa: PLC0415

    with Session(engine) as session:
        row = session.execute(
            text("SELECT 1 FROM relationships WHERE subject_id = :sid"),
            {"sid": missing_user_id},
        ).first()
    assert row is not None
