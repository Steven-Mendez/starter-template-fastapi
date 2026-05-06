"""Reusable contract suite for any KanbanCommandRepositoryPort + LookupPort.

Run against the in-memory fake AND the SQLModel/Postgres adapter by importing
``run_kanban_repository_contract(make_repo)`` from a test that supplies a SUT
factory fixture.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Protocol

from src.features.kanban.application.ports.outbound import (
    KanbanCommandRepositoryPort,
    KanbanLookupRepositoryPort,
)
from src.features.kanban.domain.errors import KanbanError
from src.features.kanban.domain.models import Board, Card, CardPriority, Column
from src.platform.shared.result import Err, Ok


class _ManagedRepo(
    KanbanCommandRepositoryPort,
    KanbanLookupRepositoryPort,
    Protocol,
): ...


RepoFactory = Callable[[], _ManagedRepo]


def _board(board_id: str = "b-1", title: str = "Roadmap") -> Board:
    return Board(
        id=board_id,
        title=title,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


def _column(column_id: str, board_id: str, position: int = 0) -> Column:
    return Column(
        id=column_id,
        board_id=board_id,
        title=f"col-{column_id}",
        position=position,
    )


def _card(card_id: str, column_id: str, position: int = 0) -> Card:
    return Card(
        id=card_id,
        column_id=column_id,
        title=f"card-{card_id}",
        description=None,
        position=position,
        priority=CardPriority.MEDIUM,
        due_at=None,
    )


def contract_save_creates_and_increments_version(make: RepoFactory) -> None:
    repo = make()
    board = _board()
    repo.save(board)
    assert board.version == 1

    found = repo.find_by_id(board.id)
    assert isinstance(found, Ok)
    assert found.value.title == "Roadmap"


def contract_save_then_find_returns_columns_and_cards(make: RepoFactory) -> None:
    repo = make()
    board = _board()
    column = _column("c-1", board.id)
    column.cards.append(_card("k-1", column.id))
    board.add_column(column)
    repo.save(board)

    result = repo.find_by_id(board.id)
    assert isinstance(result, Ok)
    columns = result.value.columns
    assert [c.id for c in columns] == ["c-1"]
    assert [k.id for k in columns[0].cards] == ["k-1"]


def contract_find_unknown_board_returns_err(make: RepoFactory) -> None:
    repo = make()
    result = repo.find_by_id("missing")
    assert isinstance(result, Err)
    assert result.error == KanbanError.BOARD_NOT_FOUND


def contract_remove_existing_board(make: RepoFactory) -> None:
    repo = make()
    board = _board()
    repo.save(board)
    result = repo.remove(board.id)
    assert isinstance(result, Ok)
    assert isinstance(repo.find_by_id(board.id), Err)


def contract_remove_unknown_board(make: RepoFactory) -> None:
    repo = make()
    result = repo.remove("missing")
    assert isinstance(result, Err)
    assert result.error == KanbanError.BOARD_NOT_FOUND


def contract_lookup_by_card_and_column(make: RepoFactory) -> None:
    repo = make()
    board = _board()
    column = _column("c-1", board.id)
    column.cards.append(_card("k-1", column.id))
    board.add_column(column)
    repo.save(board)

    assert repo.find_board_id_by_column("c-1") == board.id
    assert repo.find_board_id_by_card("k-1") == board.id
    assert repo.find_board_id_by_column("missing") is None
    assert repo.find_board_id_by_card("missing") is None


CONTRACT_SUITE = (
    contract_save_creates_and_increments_version,
    contract_save_then_find_returns_columns_and_cards,
    contract_find_unknown_board_returns_err,
    contract_remove_existing_board,
    contract_remove_unknown_board,
    contract_lookup_by_card_and_column,
)
