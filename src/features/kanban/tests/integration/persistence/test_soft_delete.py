"""Integration tests for soft-delete and restore on the kanban repository."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlmodel import Session, select

from src.features.kanban.adapters.outbound.persistence.sqlmodel.models import (
    BoardTable,
    CardTable,
    ColumnTable,
)
from src.features.kanban.adapters.outbound.persistence.sqlmodel.repository import (
    SQLModelKanbanRepository,
)
from src.features.kanban.domain.models import Board, Card, CardPriority, Column
from src.platform.shared.result import Err, Ok

pytestmark = pytest.mark.integration


def _board_with_children(board_id: str = "b-soft") -> Board:
    column = Column(id="c-1", board_id=board_id, title="Todo", position=0)
    column.cards.append(
        Card(
            id="k-1",
            column_id="c-1",
            title="Task",
            description=None,
            position=0,
            priority=CardPriority.MEDIUM,
            due_at=None,
        )
    )
    return Board(
        id=board_id,
        title="Roadmap",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        columns=[column],
    )


def test_remove_soft_deletes_and_hides_from_reads(postgres_engine: Engine) -> None:
    repo = SQLModelKanbanRepository.from_engine(postgres_engine)
    repo.save(_board_with_children())

    result = repo.remove("b-soft")
    assert isinstance(result, Ok)

    # Reads return BOARD_NOT_FOUND.
    assert isinstance(repo.find_by_id("b-soft"), Err)
    assert repo.find_board_id_by_card("k-1") is None
    assert repo.find_board_id_by_column("c-1") is None
    assert all(b.id != "b-soft" for b in repo.list_all())

    # Rows still physically present with deleted_at populated.
    with Session(postgres_engine) as s:
        board_row = s.exec(select(BoardTable).where(BoardTable.id == "b-soft")).one()
        column_row = s.exec(select(ColumnTable).where(ColumnTable.id == "c-1")).one()
        card_row = s.exec(select(CardTable).where(CardTable.id == "k-1")).one()
    assert board_row.deleted_at is not None
    assert column_row.deleted_at is not None
    assert card_row.deleted_at is not None
    # Cascade shares one deletion_id so restore can revert atomically.
    assert board_row.deletion_id == column_row.deletion_id == card_row.deletion_id


def test_remove_is_idempotent(postgres_engine: Engine) -> None:
    repo = SQLModelKanbanRepository.from_engine(postgres_engine)
    repo.save(_board_with_children("b-idempotent"))
    repo.remove("b-idempotent")

    second = repo.remove("b-idempotent")
    assert isinstance(second, Err)


def test_restore_reverses_remove(postgres_engine: Engine) -> None:
    repo = SQLModelKanbanRepository.from_engine(postgres_engine)
    repo.save(_board_with_children("b-roundtrip"))
    repo.remove("b-roundtrip")

    result = repo.restore("b-roundtrip")
    assert isinstance(result, Ok)

    found = repo.find_by_id("b-roundtrip")
    assert isinstance(found, Ok)
    assert [c.id for c in found.value.columns] == ["c-1"]
    assert [k.id for k in found.value.columns[0].cards] == ["k-1"]

    with Session(postgres_engine) as s:
        board_row = s.exec(
            select(BoardTable).where(BoardTable.id == "b-roundtrip")
        ).one()
    assert board_row.deleted_at is None
    assert board_row.deletion_id is None


def test_restore_active_board_returns_not_found(postgres_engine: Engine) -> None:
    repo = SQLModelKanbanRepository.from_engine(postgres_engine)
    repo.save(_board_with_children("b-active"))

    result = repo.restore("b-active")
    assert isinstance(result, Err)


def test_remove_stamps_actor(postgres_engine: Engine) -> None:
    repo = SQLModelKanbanRepository.from_engine(postgres_engine)
    repo.save(_board_with_children("b-actor"))
    actor = uuid4()

    repo.remove("b-actor", actor_id=actor)

    with Session(postgres_engine) as s:
        row = s.execute(
            text("SELECT updated_by FROM boards WHERE id = :id"),
            {"id": "b-actor"},
        ).one()
    assert row[0] == actor
