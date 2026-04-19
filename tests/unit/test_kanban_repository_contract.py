from __future__ import annotations

from collections.abc import Callable, Generator
from datetime import datetime
from pathlib import Path
from typing import Protocol

import pytest

from src.domain.kanban.models import Board, BoardSummary, Card, CardPriority, Column
from src.domain.shared.errors import KanbanError
from src.domain.shared.result import Err, Ok, Result
from src.infrastructure.persistence.in_memory_repository import InMemoryKanbanRepository
from src.infrastructure.persistence.sqlmodel_repository import SQLiteKanbanRepository

pytestmark = pytest.mark.unit


class RepositoryContract(Protocol):
    def close(self) -> None: ...

    def is_ready(self) -> bool: ...

    def create_board(self, title: str) -> BoardSummary: ...

    def list_boards(self) -> list[BoardSummary]: ...

    def get_board(self, board_id: str) -> Result[Board, KanbanError]: ...

    def save_board(self, board: Board) -> Result[None, KanbanError]: ...

    def create_column(
        self, board_id: str, title: str
    ) -> Result[Column, KanbanError]: ...

    def create_card(
        self,
        column_id: str,
        title: str,
        description: str | None,
        *,
        priority: CardPriority = CardPriority.MEDIUM,
        due_at: datetime | None = None,
    ) -> Result[Card, KanbanError]: ...

    def get_board_id_for_column(self, column_id: str) -> str | None: ...


@pytest.fixture(params=["inmemory", "sqlite"])
def repository_factory(
    request: pytest.FixtureRequest, tmp_path: Path
) -> Generator[Callable[[], RepositoryContract], None, None]:
    created_repositories: list[RepositoryContract] = []

    if request.param == "inmemory":

        def make_inmemory() -> RepositoryContract:
            repository = InMemoryKanbanRepository()
            created_repositories.append(repository)
            return repository

        yield make_inmemory
        return

    db_path = tmp_path / "kanban-contract.sqlite3"

    def make_sqlite() -> RepositoryContract:
        repository = SQLiteKanbanRepository(str(db_path))
        created_repositories.append(repository)
        return repository

    yield make_sqlite

    for repository in created_repositories:
        close = getattr(repository, "close", None)
        if callable(close):
            close()


def test_repository_contract_not_found_error(
    repository_factory: Callable[[], RepositoryContract],
) -> None:
    repo = repository_factory()
    response = repo.get_board("00000000-0000-4000-8000-000000000001")
    assert isinstance(response, Err)
    assert response.error is KanbanError.BOARD_NOT_FOUND


def test_repository_contract_persists_card_sequence(
    repository_factory: Callable[[], RepositoryContract],
) -> None:
    """Verify that adapters persist card ordering updates."""
    repo = repository_factory()
    board = repo.create_board("Seq")
    col = repo.create_column(board.id, "C")
    assert isinstance(col, Ok)
    c1 = repo.create_card(col.value.id, "a", None)
    c2 = repo.create_card(col.value.id, "b", None)
    assert isinstance(c1, Ok) and isinstance(c2, Ok)

    apply_sequence = getattr(repo, "apply_card_sequence", None)
    if callable(apply_sequence):
        apply_sequence(col.value.id, [c2.value.id, c1.value.id])
    else:
        board_result = repo.get_board(board.id)
        assert isinstance(board_result, Ok)
        move_error = board_result.value.move_card(
            c1.value.id,
            source_column_id=col.value.id,
            target_column_id=col.value.id,
            requested_position=1,
        )
        assert move_error is None
        assert isinstance(repo.save_board(board_result.value), Ok)

    board_r = repo.get_board(board.id)
    assert isinstance(board_r, Ok)
    seq_column = next(
        (column for column in board_r.value.columns if column.id == col.value.id),
        None,
    )
    assert seq_column is not None
    titles = [card.title for card in seq_column.cards]
    assert titles == ["b", "a"]


def test_repository_contract_get_board_id_for_column(
    repository_factory: Callable[[], RepositoryContract],
) -> None:
    repo = repository_factory()
    board = repo.create_board("A")
    col = repo.create_column(board.id, "C")
    assert isinstance(col, Ok)
    assert repo.get_board_id_for_column(col.value.id) == board.id
    assert repo.get_board_id_for_column("nonexistent") is None


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
    typed_sqlite: RepositoryContract = sqlite_repo
    typed_in_memory: RepositoryContract = in_memory_repo
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
