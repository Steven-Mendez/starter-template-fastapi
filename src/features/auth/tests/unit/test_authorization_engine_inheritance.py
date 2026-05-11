"""Unit tests for cross-resource inheritance (card → column → board).

Registers the inherited resource types (``card``, ``column``) on an
:class:`AuthorizationRegistry` whose ``parent_of`` callables read from a
pre-seeded fake. The walk uses ``card → column`` then ``column → kanban``
so the engine exercises multi-level resolution rather than a hardcoded
shortcut.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
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
from src.features.auth.application.authorization.registry import (
    AuthorizationRegistry,
)
from src.features.auth.application.authorization.types import Relationship
from src.features.auth.tests.contracts.registry_helper import make_test_registry

_SCHEMA: list[Any] = [UserTable, RelationshipTable]

pytestmark = pytest.mark.unit


@dataclass(slots=True)
class FakeChildIndex:
    """Pre-seeded parent lookup maps for the registry's ``parent_of``."""

    columns_to_boards: dict[str, str] = field(default_factory=dict)
    cards_to_columns: dict[str, str] = field(default_factory=dict)


@pytest.fixture
def child_index() -> FakeChildIndex:
    return FakeChildIndex()


@pytest.fixture
def registry(child_index: FakeChildIndex) -> AuthorizationRegistry:
    reg = make_test_registry()

    def _column_parent(column_id: str) -> tuple[str, str] | None:
        board_id = child_index.columns_to_boards.get(column_id)
        if board_id is None:
            return None
        return ("kanban", board_id)

    def _card_parent(card_id: str) -> tuple[str, str] | None:
        column_id = child_index.cards_to_columns.get(card_id)
        if column_id is None:
            return None
        return ("column", column_id)

    reg.register_parent("column", parent_of=_column_parent, inherits_from="kanban")
    reg.register_parent("card", parent_of=_card_parent, inherits_from="column")
    return reg


@pytest.fixture
def adapter(
    registry: AuthorizationRegistry,
) -> Iterator[SQLModelAuthorizationAdapter]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    for table in _SCHEMA:
        table.__table__.create(engine, checkfirst=True)
    yield SQLModelAuthorizationAdapter(engine, registry)
    engine.dispose()


def _grant(
    adapter: SQLModelAuthorizationAdapter,
    *,
    user_id: UUID,
    board_id: str,
    relation: str,
) -> None:
    adapter.write_relationships(
        [
            Relationship(
                resource_type="kanban",
                resource_id=board_id,
                relation=relation,
                subject_type="user",
                subject_id=str(user_id),
            )
        ]
    )


def test_board_reader_can_read_cards_under_the_board(
    adapter: SQLModelAuthorizationAdapter,
    child_index: FakeChildIndex,
) -> None:
    user_id = uuid4()
    board_id = str(uuid4())
    column_id = str(uuid4())
    card_id = str(uuid4())
    child_index.columns_to_boards[column_id] = board_id
    child_index.cards_to_columns[card_id] = column_id
    _grant(adapter, user_id=user_id, board_id=board_id, relation="reader")

    assert adapter.check(
        user_id=user_id, action="read", resource_type="card", resource_id=card_id
    )
    assert adapter.check(
        user_id=user_id, action="read", resource_type="column", resource_id=column_id
    )


def test_board_owner_can_update_and_delete_cards_under_the_board(
    adapter: SQLModelAuthorizationAdapter,
    child_index: FakeChildIndex,
) -> None:
    user_id = uuid4()
    board_id = str(uuid4())
    column_id = str(uuid4())
    card_id = str(uuid4())
    child_index.columns_to_boards[column_id] = board_id
    child_index.cards_to_columns[card_id] = column_id
    _grant(adapter, user_id=user_id, board_id=board_id, relation="owner")

    assert adapter.check(
        user_id=user_id, action="update", resource_type="card", resource_id=card_id
    )
    assert adapter.check(
        user_id=user_id, action="delete", resource_type="card", resource_id=card_id
    )


def test_reader_cannot_update_via_card(
    adapter: SQLModelAuthorizationAdapter,
    child_index: FakeChildIndex,
) -> None:
    user_id = uuid4()
    board_id = str(uuid4())
    column_id = str(uuid4())
    card_id = str(uuid4())
    child_index.columns_to_boards[column_id] = board_id
    child_index.cards_to_columns[card_id] = column_id
    _grant(adapter, user_id=user_id, board_id=board_id, relation="reader")

    assert not adapter.check(
        user_id=user_id, action="update", resource_type="card", resource_id=card_id
    )


def test_unknown_card_returns_false_without_raising(
    adapter: SQLModelAuthorizationAdapter,
) -> None:
    """Missing parent → denied check; never an exception."""
    assert (
        adapter.check(
            user_id=uuid4(),
            action="read",
            resource_type="card",
            resource_id="missing",
        )
        is False
    )
    assert (
        adapter.check(
            user_id=uuid4(),
            action="read",
            resource_type="column",
            resource_id="missing",
        )
        is False
    )


def test_no_tuples_are_written_for_card_or_column_inheritance(
    adapter: SQLModelAuthorizationAdapter,
    child_index: FakeChildIndex,
) -> None:
    """Granting board access SHALL NOT materialize per-card or per-column rows."""
    from sqlalchemy import text  # noqa: PLC0415
    from sqlmodel import Session  # noqa: PLC0415

    user_id = uuid4()
    board_id = str(uuid4())
    column_id = str(uuid4())
    card_id = str(uuid4())
    child_index.columns_to_boards[column_id] = board_id
    child_index.cards_to_columns[card_id] = column_id
    _grant(adapter, user_id=user_id, board_id=board_id, relation="writer")

    engine = adapter._engine  # type: ignore[attr-defined]
    with Session(engine) as session:
        rows = list(
            session.execute(text("SELECT resource_type, relation FROM relationships"))
        )
    assert all(row[0] == "kanban" for row in rows)
    assert {row[1] for row in rows} == {"writer"}
