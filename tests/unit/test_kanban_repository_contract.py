from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from kanban.errors import KanbanError
from kanban.repository import InMemoryKanbanRepository, KanbanRepository
from kanban.result import Err, Ok
from kanban.sqlite_repository import SQLiteKanbanRepository

pytestmark = pytest.mark.unit


@pytest.fixture(params=["inmemory", "sqlite"])
def repository_factory(
    request: pytest.FixtureRequest, tmp_path: Path
) -> Callable[[], KanbanRepository]:
    if request.param == "inmemory":
        return InMemoryKanbanRepository

    db_path = tmp_path / "kanban-contract.sqlite3"

    def make_sqlite() -> KanbanRepository:
        return SQLiteKanbanRepository(str(db_path))

    return make_sqlite


def test_repository_contract_not_found_error(
    repository_factory: Callable[[], KanbanRepository],
) -> None:
    repo = repository_factory()
    response = repo.get_board("00000000-0000-4000-8000-000000000001")
    assert isinstance(response, Err)
    assert response.error is KanbanError.BOARD_NOT_FOUND


def test_repository_contract_invalid_cross_board_move(
    repository_factory: Callable[[], KanbanRepository],
) -> None:
    repo = repository_factory()
    board_a = repo.create_board("A")
    board_b = repo.create_board("B")
    col_a = repo.create_column(board_a.id, "A1")
    col_b = repo.create_column(board_b.id, "B1")
    assert isinstance(col_a, Ok)
    assert isinstance(col_b, Ok)
    card = repo.create_card(col_a.value.id, "c", None)
    assert isinstance(card, Ok)

    moved = repo.update_card(card.value.id, column_id=col_b.value.id)
    assert isinstance(moved, Err)
    assert moved.error is KanbanError.INVALID_CARD_MOVE


def test_sqlite_repository_persists_data_across_instances(tmp_path: Path) -> None:
    db_path = tmp_path / "kanban-persist.sqlite3"
    first = SQLiteKanbanRepository(str(db_path))
    created = first.create_board("Persistent")
    second = SQLiteKanbanRepository(str(db_path))
    boards = second.list_boards()
    assert any(board.id == created.id for board in boards)
