"""Tests for KanbanCommandHandlers — validation & reorder orchestration.

These tests exercise the business-rule validations and card-movement
orchestration that now live in the application layer (handle_patch_card),
ensuring that domain services are invoked correctly and the results are
propagated back to the caller.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.application.commands import (
    CreateBoardCommand,
    CreateCardCommand,
    CreateColumnCommand,
    KanbanCommandHandlers,
    PatchCardCommand,
)
from src.application.queries import GetBoardQuery, KanbanQueryHandlers
from src.domain.kanban.models import CardPriority
from src.domain.shared.errors import KanbanError
from src.domain.shared.result import Err, Ok
from src.infrastructure.persistence.in_memory_repository import InMemoryKanbanRepository

pytestmark = pytest.mark.unit


def _setup():
    """Create a fresh in-memory repo and command/query handlers."""
    repo = InMemoryKanbanRepository()
    commands = KanbanCommandHandlers(repository=repo)
    queries = KanbanQueryHandlers(repository=repo)
    return repo, commands, queries


# ---------- Validation: cross-board move ----------


def test_card_cannot_move_to_column_on_another_board() -> None:
    _, commands, _ = _setup()
    board_a = commands.handle_create_board(CreateBoardCommand(title="One"))
    board_b = commands.handle_create_board(CreateBoardCommand(title="Two"))
    col_a = commands.handle_create_column(
        CreateColumnCommand(board_id=board_a.id, title="x")
    )
    col_b = commands.handle_create_column(
        CreateColumnCommand(board_id=board_b.id, title="y")
    )
    assert isinstance(col_a, Ok) and isinstance(col_b, Ok)
    card = commands.handle_create_card(
        CreateCardCommand(
            column_id=col_a.value.id,
            title="c",
            description=None,
            priority=CardPriority.MEDIUM,
            due_at=None,
        )
    )
    assert isinstance(card, Ok)
    r = commands.handle_patch_card(
        PatchCardCommand(card_id=card.value.id, column_id=col_b.value.id)
    )
    assert isinstance(r, Err)
    assert r.error is KanbanError.INVALID_CARD_MOVE


# ---------- Validation: nonexistent target ----------


def test_move_card_fails_when_target_column_does_not_exist() -> None:
    _, commands, _ = _setup()
    board = commands.handle_create_board(CreateBoardCommand(title="Targets"))
    col = commands.handle_create_column(
        CreateColumnCommand(board_id=board.id, title="c")
    )
    assert isinstance(col, Ok)
    card = commands.handle_create_card(
        CreateCardCommand(
            column_id=col.value.id,
            title="c",
            description=None,
            priority=CardPriority.MEDIUM,
            due_at=None,
        )
    )
    assert isinstance(card, Ok)
    r = commands.handle_patch_card(
        PatchCardCommand(
            card_id=card.value.id,
            column_id="00000000-0000-4000-8000-000000000099",
        )
    )
    assert isinstance(r, Err)
    assert r.error is KanbanError.COLUMN_NOT_FOUND


# ---------- Same-board move ----------


def test_card_can_move_between_columns_on_same_board() -> None:
    _, commands, queries = _setup()
    board = commands.handle_create_board(CreateBoardCommand(title="Move"))
    col_a = commands.handle_create_column(
        CreateColumnCommand(board_id=board.id, title="A")
    )
    col_b = commands.handle_create_column(
        CreateColumnCommand(board_id=board.id, title="B")
    )
    assert isinstance(col_a, Ok) and isinstance(col_b, Ok)
    card = commands.handle_create_card(
        CreateCardCommand(
            column_id=col_a.value.id,
            title="Move me",
            description=None,
            priority=CardPriority.MEDIUM,
            due_at=None,
        )
    )
    assert isinstance(card, Ok)
    moved = commands.handle_patch_card(
        PatchCardCommand(card_id=card.value.id, column_id=col_b.value.id)
    )
    assert isinstance(moved, Ok)
    assert moved.value.column_id == col_b.value.id
    detail = queries.handle_get_board(GetBoardQuery(board_id=board.id))
    assert isinstance(detail, Ok)
    by_title = {c.title: c for c in detail.value.columns}
    assert len(by_title["A"].cards) == 0
    assert len(by_title["B"].cards) == 1


# ---------- Reorder within column ----------


def test_card_order_within_column_follows_position_updates() -> None:
    _, commands, queries = _setup()
    board = commands.handle_create_board(CreateBoardCommand(title="Reorder"))
    col = commands.handle_create_column(
        CreateColumnCommand(board_id=board.id, title="c")
    )
    assert isinstance(col, Ok)
    c1 = commands.handle_create_card(
        CreateCardCommand(
            column_id=col.value.id,
            title="a",
            description=None,
            priority=CardPriority.MEDIUM,
            due_at=None,
        )
    )
    c2 = commands.handle_create_card(
        CreateCardCommand(
            column_id=col.value.id,
            title="b",
            description=None,
            priority=CardPriority.MEDIUM,
            due_at=None,
        )
    )
    assert isinstance(c1, Ok) and isinstance(c2, Ok)
    reordered = commands.handle_patch_card(
        PatchCardCommand(card_id=c1.value.id, position=1)
    )
    assert isinstance(reordered, Ok)
    detail = queries.handle_get_board(GetBoardQuery(board_id=board.id))
    assert isinstance(detail, Ok)
    titles = [card.title for card in detail.value.columns[0].cards]
    assert titles == ["b", "a"]


# ---------- Preservation: priority is not lost during move ----------


def test_priority_preserved_when_moving_between_columns() -> None:
    _, commands, _ = _setup()
    board = commands.handle_create_board(CreateBoardCommand(title="Prio"))
    col_a = commands.handle_create_column(
        CreateColumnCommand(board_id=board.id, title="A")
    )
    col_b = commands.handle_create_column(
        CreateColumnCommand(board_id=board.id, title="B")
    )
    assert isinstance(col_a, Ok) and isinstance(col_b, Ok)
    card = commands.handle_create_card(
        CreateCardCommand(
            column_id=col_a.value.id,
            title="move",
            description=None,
            priority=CardPriority.HIGH,
            due_at=None,
        )
    )
    assert isinstance(card, Ok)
    moved = commands.handle_patch_card(
        PatchCardCommand(card_id=card.value.id, column_id=col_b.value.id)
    )
    assert isinstance(moved, Ok)
    assert moved.value.priority is CardPriority.HIGH


# ---------- Preservation: due_at is not lost during move ----------


def test_due_at_preserved_when_moving_between_columns() -> None:
    _, commands, _ = _setup()
    board = commands.handle_create_board(CreateBoardCommand(title="Due"))
    col_a = commands.handle_create_column(
        CreateColumnCommand(board_id=board.id, title="A")
    )
    col_b = commands.handle_create_column(
        CreateColumnCommand(board_id=board.id, title="B")
    )
    assert isinstance(col_a, Ok) and isinstance(col_b, Ok)
    when = datetime(2034, 5, 5, 8, 0, tzinfo=timezone.utc)
    card = commands.handle_create_card(
        CreateCardCommand(
            column_id=col_a.value.id,
            title="move",
            description=None,
            priority=CardPriority.MEDIUM,
            due_at=when,
        )
    )
    assert isinstance(card, Ok)
    moved = commands.handle_patch_card(
        PatchCardCommand(card_id=card.value.id, column_id=col_b.value.id)
    )
    assert isinstance(moved, Ok)
    assert moved.value.due_at == when
