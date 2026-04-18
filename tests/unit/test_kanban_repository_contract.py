from __future__ import annotations

from collections.abc import Callable, Generator
from pathlib import Path

import pytest

from src.application.ports.repository import KanbanRepository
from src.domain.shared.errors import KanbanError
from src.domain.shared.result import Err, Ok
from src.infrastructure.persistence.in_memory_repository import InMemoryKanbanRepository
from src.infrastructure.persistence.sqlmodel_repository import SQLiteKanbanRepository

pytestmark = pytest.mark.unit


@pytest.fixture(params=["inmemory", "sqlite"])
def repository_factory(
    request: pytest.FixtureRequest, tmp_path: Path
) -> Generator[Callable[[], KanbanRepository], None, None]:
    created_repositories: list[KanbanRepository] = []

    if request.param == "inmemory":

        def make_inmemory() -> KanbanRepository:
            repository = InMemoryKanbanRepository()
            created_repositories.append(repository)
            return repository

        yield make_inmemory
        return

    db_path = tmp_path / "kanban-contract.sqlite3"

    def make_sqlite() -> KanbanRepository:
        repository = SQLiteKanbanRepository(str(db_path))
        created_repositories.append(repository)
        return repository

    yield make_sqlite

    for repository in created_repositories:
        close = getattr(repository, "close", None)
        if callable(close):
            close()


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
    first.close()
    second.close()


def test_repository_implementations_conform_to_protocol(tmp_path: Path) -> None:
    sqlite_repo = SQLiteKanbanRepository(str(tmp_path / "repo-protocol.sqlite3"))
    in_memory_repo = InMemoryKanbanRepository()
    typed_sqlite: KanbanRepository = sqlite_repo
    typed_in_memory: KanbanRepository = in_memory_repo
    assert typed_sqlite.is_ready() is True
    assert typed_in_memory.is_ready() is True
    sqlite_repo.close()


def test_sqlite_repository_close_is_idempotent(tmp_path: Path) -> None:
    repository = SQLiteKanbanRepository(str(tmp_path / "close-idempotent.sqlite3"))
    repository.close()
    repository.close()
    assert repository.is_ready() is False


def test_sqlite_repository_context_manager_closes_connection(tmp_path: Path) -> None:
    with SQLiteKanbanRepository(
        str(tmp_path / "context-manager.sqlite3")
    ) as repository:
        board = repository.create_board("ctx")
        assert board.id
    assert repository.is_ready() is False
