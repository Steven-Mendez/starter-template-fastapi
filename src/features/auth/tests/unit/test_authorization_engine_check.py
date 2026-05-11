"""Unit tests for ``SQLModelAuthorizationAdapter.check`` over a SQLite fixture.

These exercise the engine's hierarchy resolution at the kanban resource
level. Cross-resource inheritance is covered by
``test_authorization_engine_inheritance.py``.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import create_engine

from src.features.auth.adapters.outbound.authorization.sqlmodel import (
    SQLModelAuthorizationAdapter,
)
from src.features.auth.adapters.outbound.persistence.sqlmodel.models import (
    RelationshipTable,
    UserTable,
)
from src.features.auth.application.authorization.errors import UnknownActionError
from src.features.auth.application.authorization.types import Relationship
from src.features.auth.tests.contracts.registry_helper import make_test_registry

_SCHEMA: list[Any] = [UserTable, RelationshipTable]

pytestmark = pytest.mark.unit


@pytest.fixture
def adapter() -> Iterator[SQLModelAuthorizationAdapter]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    for table in _SCHEMA:
        table.__table__.create(engine, checkfirst=True)
    yield SQLModelAuthorizationAdapter(engine, make_test_registry())
    engine.dispose()


@pytest.fixture
def user_id() -> UUID:
    return uuid4()


@pytest.fixture
def board_id() -> str:
    return str(uuid4())


def test_owner_satisfies_read_update_and_delete(
    adapter: SQLModelAuthorizationAdapter, user_id: UUID, board_id: str
) -> None:
    adapter.write_relationships(
        [
            Relationship(
                resource_type="kanban",
                resource_id=board_id,
                relation="owner",
                subject_type="user",
                subject_id=str(user_id),
            )
        ]
    )
    for action in ("read", "update", "delete"):
        assert adapter.check(
            user_id=user_id,
            action=action,
            resource_type="kanban",
            resource_id=board_id,
        ), action


def test_writer_satisfies_read_and_update_but_not_delete(
    adapter: SQLModelAuthorizationAdapter, user_id: UUID, board_id: str
) -> None:
    adapter.write_relationships(
        [
            Relationship(
                resource_type="kanban",
                resource_id=board_id,
                relation="writer",
                subject_type="user",
                subject_id=str(user_id),
            )
        ]
    )
    assert adapter.check(
        user_id=user_id, action="read", resource_type="kanban", resource_id=board_id
    )
    assert adapter.check(
        user_id=user_id, action="update", resource_type="kanban", resource_id=board_id
    )
    assert not adapter.check(
        user_id=user_id, action="delete", resource_type="kanban", resource_id=board_id
    )


def test_reader_satisfies_only_read(
    adapter: SQLModelAuthorizationAdapter, user_id: UUID, board_id: str
) -> None:
    adapter.write_relationships(
        [
            Relationship(
                resource_type="kanban",
                resource_id=board_id,
                relation="reader",
                subject_type="user",
                subject_id=str(user_id),
            )
        ]
    )
    assert adapter.check(
        user_id=user_id, action="read", resource_type="kanban", resource_id=board_id
    )
    assert not adapter.check(
        user_id=user_id, action="update", resource_type="kanban", resource_id=board_id
    )


def test_no_tuple_denies_every_action(
    adapter: SQLModelAuthorizationAdapter, user_id: UUID, board_id: str
) -> None:
    for action in ("read", "update", "delete"):
        assert not adapter.check(
            user_id=user_id,
            action=action,
            resource_type="kanban",
            resource_id=board_id,
        )


def test_check_is_user_scoped(
    adapter: SQLModelAuthorizationAdapter, board_id: str
) -> None:
    grantee = uuid4()
    other = uuid4()
    adapter.write_relationships(
        [
            Relationship(
                resource_type="kanban",
                resource_id=board_id,
                relation="owner",
                subject_type="user",
                subject_id=str(grantee),
            )
        ]
    )
    assert adapter.check(
        user_id=grantee, action="read", resource_type="kanban", resource_id=board_id
    )
    assert not adapter.check(
        user_id=other, action="read", resource_type="kanban", resource_id=board_id
    )


def test_system_admin_satisfies_system_actions(
    adapter: SQLModelAuthorizationAdapter, user_id: UUID
) -> None:
    adapter.write_relationships(
        [
            Relationship(
                resource_type="system",
                resource_id="main",
                relation="admin",
                subject_type="user",
                subject_id=str(user_id),
            )
        ]
    )
    for action in ("manage_users", "read_audit"):
        assert adapter.check(
            user_id=user_id,
            action=action,
            resource_type="system",
            resource_id="main",
        ), action


def test_duplicate_writes_are_idempotent(
    adapter: SQLModelAuthorizationAdapter, user_id: UUID, board_id: str
) -> None:
    tup = Relationship(
        resource_type="kanban",
        resource_id=board_id,
        relation="reader",
        subject_type="user",
        subject_id=str(user_id),
    )
    adapter.write_relationships([tup])
    adapter.write_relationships([tup])  # second call must not raise
    assert adapter.check(
        user_id=user_id, action="read", resource_type="kanban", resource_id=board_id
    )


def test_delete_removes_the_grant(
    adapter: SQLModelAuthorizationAdapter, user_id: UUID, board_id: str
) -> None:
    tup = Relationship(
        resource_type="kanban",
        resource_id=board_id,
        relation="owner",
        subject_type="user",
        subject_id=str(user_id),
    )
    adapter.write_relationships([tup])
    assert adapter.check(
        user_id=user_id, action="read", resource_type="kanban", resource_id=board_id
    )
    adapter.delete_relationships([tup])
    assert not adapter.check(
        user_id=user_id, action="read", resource_type="kanban", resource_id=board_id
    )


def test_check_on_unregistered_resource_type_raises(
    adapter: SQLModelAuthorizationAdapter, user_id: UUID
) -> None:
    """A check for a resource type no feature registered surfaces as a 500."""
    with pytest.raises(UnknownActionError):
        adapter.check(
            user_id=user_id,
            action="read",
            resource_type="orgs",
            resource_id=str(uuid4()),
        )
