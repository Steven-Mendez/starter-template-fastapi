from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.domain.kanban.models import Board, Card, CardPriority, Column
from src.infrastructure.persistence.sqlmodel.mappers import (
    board_domain_to_table,
    board_table_to_summary,
    card_domain_to_table,
    card_table_to_domain,
    column_domain_to_table,
)
from src.infrastructure.persistence.sqlmodel.models import BoardTable, CardTable

pytestmark = pytest.mark.unit


def test_card_table_to_domain_maps_all_fields() -> None:
    due_at = datetime(2026, 4, 1, 10, 30, tzinfo=timezone.utc)
    row = CardTable(
        id="card-1",
        column_id="column-1",
        title="Write mapper tests",
        description="Cover fields and enum conversion",
        position=2,
        priority="high",
        due_at=due_at,
    )

    card = card_table_to_domain(row)

    assert card.id == "card-1"
    assert card.column_id == "column-1"
    assert card.title == "Write mapper tests"
    assert card.description == "Cover fields and enum conversion"
    assert card.position == 2
    assert card.priority is CardPriority.HIGH
    assert card.due_at == due_at


def test_card_table_to_domain_normalizes_naive_datetime_to_utc() -> None:
    row = CardTable(
        id="card-2",
        column_id="column-1",
        title="Normalize due date",
        description=None,
        position=0,
        priority="medium",
        due_at=datetime(2026, 4, 1, 10, 30),
    )

    card = card_table_to_domain(row)

    assert card.due_at is not None
    assert card.due_at.tzinfo == timezone.utc


def test_card_domain_to_table_maps_priority_as_string() -> None:
    card = Card(
        id="card-3",
        column_id="column-ignored",
        title="Persist card",
        description=None,
        position=1,
        priority=CardPriority.HIGH,
        due_at=None,
    )

    row = card_domain_to_table(card, column_id="column-2")

    assert row.id == "card-3"
    assert row.column_id == "column-2"
    assert row.priority == "high"


def test_board_table_to_summary_maps_fields() -> None:
    created_at = datetime(2026, 4, 1, 10, 30)
    row = BoardTable(id="board-1", title="Planning", created_at=created_at)

    summary = board_table_to_summary(row)

    assert summary.id == "board-1"
    assert summary.title == "Planning"
    assert summary.created_at.tzinfo == timezone.utc


def test_domain_to_table_mappers_keep_identity_fields() -> None:
    board = Board(
        id="board-2",
        title="Execution",
        created_at=datetime(2026, 4, 1, 10, 30, tzinfo=timezone.utc),
        columns=[],
    )
    column = Column(
        id="column-9",
        board_id="board-ignored",
        title="Doing",
        position=3,
        cards=[],
    )

    board_row = board_domain_to_table(board)
    column_row = column_domain_to_table(column, board_id="board-2")

    assert board_row.id == "board-2"
    assert board_row.title == "Execution"
    assert column_row.id == "column-9"
    assert column_row.board_id == "board-2"
