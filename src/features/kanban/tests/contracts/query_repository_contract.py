"""Contract suite for KanbanQueryRepositoryPort implementations."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Protocol

from src.features.kanban.application.ports.outbound import (
    KanbanCommandRepositoryPort,
    KanbanQueryRepositoryPort,
)
from src.features.kanban.domain.errors import KanbanError
from src.features.kanban.domain.models import Board, Card, CardPriority, Column
from src.platform.shared.result import Err, Ok


class _ReadWrite(KanbanCommandRepositoryPort, KanbanQueryRepositoryPort, Protocol): ...


RepoFactory = Callable[[], _ReadWrite]


def _board(board_id: str, title: str) -> Board:
    return Board(
        id=board_id,
        title=title,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


def contract_list_all_empty(make: RepoFactory) -> None:
    repo = make()
    assert repo.list_all() == []


def contract_list_all_returns_summaries(make: RepoFactory) -> None:
    repo = make()
    repo.save(_board("a", "A"))
    repo.save(_board("b", "B"))
    summaries = repo.list_all()
    assert sorted(s.title for s in summaries) == ["A", "B"]


def contract_find_card_returns_card(make: RepoFactory) -> None:
    repo = make()
    board = _board("b", "B")
    column = Column(id="c", board_id=board.id, title="t", position=0)
    column.cards.append(
        Card(
            id="k",
            column_id=column.id,
            title="task",
            description=None,
            position=0,
            priority=CardPriority.MEDIUM,
            due_at=None,
        )
    )
    board.add_column(column)
    repo.save(board)

    result = repo.find_card_by_id("k")
    assert isinstance(result, Ok)
    assert result.value.title == "task"


def contract_find_card_missing(make: RepoFactory) -> None:
    repo = make()
    result = repo.find_card_by_id("missing")
    assert isinstance(result, Err)
    assert result.error == KanbanError.CARD_NOT_FOUND


CONTRACT_SUITE = (
    contract_list_all_empty,
    contract_list_all_returns_summaries,
    contract_find_card_returns_card,
    contract_find_card_missing,
)
