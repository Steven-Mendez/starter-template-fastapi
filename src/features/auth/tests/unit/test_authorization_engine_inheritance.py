"""Unit tests for cross-resource inheritance (card → column → board)."""

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
from src.features.auth.application.authorization.types import Relationship

_SCHEMA: list[Any] = [UserTable, RelationshipTable]

pytestmark = pytest.mark.unit


@dataclass(slots=True)
class FakeParentResolver:
    """Minimal ``ParentResolver`` for unit tests; pre-seeded with parent maps."""

    columns_to_boards: dict[str, str] = field(default_factory=dict)
    cards_to_boards: dict[str, str] = field(default_factory=dict)

    def board_id_for_card(self, card_id: str) -> str | None:
        return self.cards_to_boards.get(card_id)

    def board_id_for_column(self, column_id: str) -> str | None:
        return self.columns_to_boards.get(column_id)


@pytest.fixture
def parent_resolver() -> FakeParentResolver:
    return FakeParentResolver()


@pytest.fixture
def adapter(
    parent_resolver: FakeParentResolver,
) -> Iterator[SQLModelAuthorizationAdapter]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    for table in _SCHEMA:
        table.__table__.create(engine, checkfirst=True)
    yield SQLModelAuthorizationAdapter(engine, parent_resolver=parent_resolver)
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
    parent_resolver: FakeParentResolver,
) -> None:
    user_id = uuid4()
    board_id = str(uuid4())
    column_id = str(uuid4())
    card_id = str(uuid4())
    parent_resolver.columns_to_boards[column_id] = board_id
    parent_resolver.cards_to_boards[card_id] = board_id
    _grant(adapter, user_id=user_id, board_id=board_id, relation="reader")

    assert adapter.check(
        user_id=user_id, action="read", resource_type="card", resource_id=card_id
    )
    assert adapter.check(
        user_id=user_id, action="read", resource_type="column", resource_id=column_id
    )


def test_board_owner_can_update_and_delete_cards_under_the_board(
    adapter: SQLModelAuthorizationAdapter,
    parent_resolver: FakeParentResolver,
) -> None:
    user_id = uuid4()
    board_id = str(uuid4())
    card_id = str(uuid4())
    parent_resolver.cards_to_boards[card_id] = board_id
    _grant(adapter, user_id=user_id, board_id=board_id, relation="owner")

    assert adapter.check(
        user_id=user_id, action="update", resource_type="card", resource_id=card_id
    )
    assert adapter.check(
        user_id=user_id, action="delete", resource_type="card", resource_id=card_id
    )


def test_reader_cannot_update_via_card(
    adapter: SQLModelAuthorizationAdapter,
    parent_resolver: FakeParentResolver,
) -> None:
    user_id = uuid4()
    board_id = str(uuid4())
    card_id = str(uuid4())
    parent_resolver.cards_to_boards[card_id] = board_id
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
    parent_resolver: FakeParentResolver,
) -> None:
    """Granting board access SHALL NOT materialize per-card or per-column rows."""
    from sqlalchemy import text  # noqa: PLC0415
    from sqlmodel import Session  # noqa: PLC0415

    user_id = uuid4()
    board_id = str(uuid4())
    parent_resolver.cards_to_boards[str(uuid4())] = board_id
    _grant(adapter, user_id=user_id, board_id=board_id, relation="writer")

    # Direct DB inspection to confirm no inferred tuples leaked into storage.
    engine = adapter._engine  # type: ignore[attr-defined]
    with Session(engine) as session:
        rows = list(
            session.execute(text("SELECT resource_type, relation FROM relationships"))
        )
    assert all(row[0] == "kanban" for row in rows)
    assert {row[1] for row in rows} == {"writer"}
