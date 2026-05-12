"""Unit tests for ``lookup_resources`` and ``lookup_subjects``."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import create_engine

from src.features.authentication.adapters.outbound.persistence.sqlmodel.models import (
    UserTable,
)
from src.features.authorization.adapters.outbound.sqlmodel import (
    SQLModelAuthorizationAdapter,
)
from src.features.authorization.application.types import Relationship
from src.features.authorization.tests.contracts.fake_user_authz_version import (
    FakeUserAuthzVersionPort,
)
from src.features.authorization.tests.contracts.registry_helper import (
    make_test_registry,
)
from src.platform.persistence.sqlmodel.authorization.models import RelationshipTable

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
    yield SQLModelAuthorizationAdapter(
        engine, make_test_registry(), FakeUserAuthzVersionPort()
    )
    engine.dispose()


def _tuple(*, resource_id: str, relation: str, user_id: UUID) -> Relationship:
    return Relationship(
        resource_type="thing",
        resource_id=resource_id,
        relation=relation,
        subject_type="user",
        subject_id=str(user_id),
    )


def test_lookup_resources_returns_boards_with_at_least_reader(
    adapter: SQLModelAuthorizationAdapter,
) -> None:
    user_id = uuid4()
    other = uuid4()
    b1, b2, b3, b4 = (str(uuid4()) for _ in range(4))
    adapter.write_relationships(
        [
            _tuple(resource_id=b1, relation="owner", user_id=user_id),
            _tuple(resource_id=b2, relation="writer", user_id=user_id),
            _tuple(resource_id=b3, relation="reader", user_id=user_id),
            _tuple(resource_id=b4, relation="reader", user_id=other),
        ]
    )
    found = adapter.lookup_resources(
        user_id=user_id, action="read", resource_type="thing"
    )
    assert set(found) == {b1, b2, b3}
    assert b4 not in found


def test_lookup_resources_filters_by_action(
    adapter: SQLModelAuthorizationAdapter,
) -> None:
    user_id = uuid4()
    b_owner, b_writer, b_reader = (str(uuid4()) for _ in range(3))
    adapter.write_relationships(
        [
            _tuple(resource_id=b_owner, relation="owner", user_id=user_id),
            _tuple(resource_id=b_writer, relation="writer", user_id=user_id),
            _tuple(resource_id=b_reader, relation="reader", user_id=user_id),
        ]
    )
    delete = adapter.lookup_resources(
        user_id=user_id, action="delete", resource_type="thing"
    )
    assert delete == [b_owner]

    update = adapter.lookup_resources(
        user_id=user_id, action="update", resource_type="thing"
    )
    assert set(update) == {b_owner, b_writer}


def test_lookup_resources_dedups_when_user_holds_multiple_relations(
    adapter: SQLModelAuthorizationAdapter,
) -> None:
    user_id = uuid4()
    board_id = str(uuid4())
    adapter.write_relationships(
        [
            _tuple(resource_id=board_id, relation="owner", user_id=user_id),
            _tuple(resource_id=board_id, relation="reader", user_id=user_id),
        ]
    )
    found = adapter.lookup_resources(
        user_id=user_id, action="read", resource_type="thing"
    )
    assert found == [board_id]


def test_lookup_resources_caps_at_the_limit(
    adapter: SQLModelAuthorizationAdapter,
) -> None:
    user_id = uuid4()
    boards = [str(uuid4()) for _ in range(150)]
    adapter.write_relationships(
        [_tuple(resource_id=b, relation="reader", user_id=user_id) for b in boards]
    )
    default = adapter.lookup_resources(
        user_id=user_id, action="read", resource_type="thing"
    )
    assert len(default) == 100  # default limit
    capped = adapter.lookup_resources(
        user_id=user_id, action="read", resource_type="thing", limit=10
    )
    assert len(capped) == 10


def test_lookup_resources_max_limit_is_500(
    adapter: SQLModelAuthorizationAdapter,
) -> None:
    user_id = uuid4()
    boards = [str(uuid4()) for _ in range(600)]
    adapter.write_relationships(
        [_tuple(resource_id=b, relation="reader", user_id=user_id) for b in boards]
    )
    very_high = adapter.lookup_resources(
        user_id=user_id, action="read", resource_type="thing", limit=10_000
    )
    assert len(very_high) == 500


def test_lookup_subjects_returns_users_with_relation_or_higher(
    adapter: SQLModelAuthorizationAdapter,
) -> None:
    board_id = str(uuid4())
    owner = uuid4()
    writer = uuid4()
    reader = uuid4()
    other = uuid4()
    adapter.write_relationships(
        [
            _tuple(resource_id=board_id, relation="owner", user_id=owner),
            _tuple(resource_id=board_id, relation="writer", user_id=writer),
            _tuple(resource_id=board_id, relation="reader", user_id=reader),
            _tuple(resource_id=str(uuid4()), relation="owner", user_id=other),
        ]
    )
    readers = set(
        adapter.lookup_subjects(
            resource_type="thing", resource_id=board_id, relation="reader"
        )
    )
    assert readers == {owner, writer, reader}

    only_owners = adapter.lookup_subjects(
        resource_type="thing", resource_id=board_id, relation="owner"
    )
    assert only_owners == [owner]
