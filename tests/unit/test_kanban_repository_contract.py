from __future__ import annotations

import uuid
from collections.abc import Callable, Generator
from datetime import datetime
from pathlib import Path
from typing import Protocol

import pytest

from src.application.shared.readiness import ReadinessProbe
from src.domain.kanban.models import Board, BoardSummary, Card, CardPriority, Column
from src.domain.shared.errors import KanbanError
from src.domain.shared.result import Err, Ok, Result
from src.infrastructure.persistence.in_memory_repository import InMemoryKanbanRepository
from src.infrastructure.persistence.lifecycle import ClosableResource
from src.infrastructure.persistence.sqlmodel_repository import SQLiteKanbanRepository

pytestmark = pytest.mark.unit


class RepositoryContract(Protocol):
    def create_board(self, title: str) -> BoardSummary: ...

    def list_boards(self) -> list[BoardSummary]: ...

    def get_board(self, board_id: str) -> Result[Board, KanbanError]: ...

    def save_board(self, board: Board) -> Result[None, KanbanError]: ...

    def find_board_id_by_column(self, column_id: str) -> str | None: ...


def _append_column(
    repository: RepositoryContract,
    board_id: str,
    title: str,
) -> Result[Column, KanbanError]:
    board_result = repository.get_board(board_id)
    if isinstance(board_result, Err):
        return Err(board_result.error)

    board = board_result.value
    column = Column(
        id=str(uuid.uuid4()),
        board_id=board_id,
        title=title,
        position=max((candidate.position for candidate in board.columns), default=-1)
        + 1,
        cards=[],
    )
    board.columns.append(column)
    save_result = repository.save_board(board)
    if isinstance(save_result, Err):
        return save_result
    return Ok(column)


def _append_card(
    repository: RepositoryContract,
    column_id: str,
    title: str,
    description: str | None,
    *,
    priority: CardPriority = CardPriority.MEDIUM,
    due_at: datetime | None = None,
) -> Result[Card, KanbanError]:
    board_id = repository.find_board_id_by_column(column_id)
    if board_id is None:
        return Err(KanbanError.COLUMN_NOT_FOUND)

    board_result = repository.get_board(board_id)
    if isinstance(board_result, Err):
        return board_result
    board = board_result.value

    column = next(
        (candidate for candidate in board.columns if candidate.id == column_id), None
    )
    if column is None:
        return Err(KanbanError.COLUMN_NOT_FOUND)

    card = Card(
        id=str(uuid.uuid4()),
        column_id=column_id,
        title=title,
        description=description,
        position=0,
        priority=priority,
        due_at=due_at,
    )
    column.insert_card(card)
    save_result = repository.save_board(board)
    if isinstance(save_result, Err):
        return save_result
    return Ok(card)


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
    col = _append_column(repo, board.id, "C")
    assert isinstance(col, Ok)
    c1 = _append_card(repo, col.value.id, "a", None)
    c2 = _append_card(repo, col.value.id, "b", None)
    assert isinstance(c1, Ok) and isinstance(c2, Ok)

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


def test_repository_contract_find_board_id_by_column(
    repository_factory: Callable[[], RepositoryContract],
) -> None:
    repo = repository_factory()
    board = repo.create_board("A")
    col = _append_column(repo, board.id, "C")
    assert isinstance(col, Ok)
    assert repo.find_board_id_by_column(col.value.id) == board.id
    assert repo.find_board_id_by_column("nonexistent") is None


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

    created_sqlite = typed_sqlite.create_board("contract-sqlite")
    assert created_sqlite.id
    assert any(board.id == created_sqlite.id for board in typed_sqlite.list_boards())

    created_inmemory = typed_in_memory.create_board("contract")
    assert created_inmemory.id
    assert any(
        board.id == created_inmemory.id for board in typed_in_memory.list_boards()
    )

    sqlite_probe: ReadinessProbe = sqlite_repo
    in_memory_probe: ReadinessProbe = in_memory_repo
    assert sqlite_probe.is_ready() is True
    assert in_memory_probe.is_ready() is True

    sqlite_lifecycle: ClosableResource = sqlite_repo
    in_memory_lifecycle: ClosableResource = in_memory_repo
    sqlite_lifecycle.close()
    in_memory_lifecycle.close()


def test_sqlite_repository_close_is_idempotent(tmp_path: Path) -> None:
    repository = SQLiteKanbanRepository(str(tmp_path / "close-idempotent.sqlite3"))
    lifecycle: ClosableResource = repository
    probe: ReadinessProbe = repository
    lifecycle.close()
    lifecycle.close()
    assert probe.is_ready() is False


def test_sqlite_repository_context_manager_closes_connection(tmp_path: Path) -> None:
    with SQLiteKanbanRepository(
        str(tmp_path / "context-manager.sqlite3")
    ) as repository:
        board = repository.create_board("ctx")
        assert board.id
    assert repository.is_ready() is False
