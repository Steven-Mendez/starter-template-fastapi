from __future__ import annotations

import uuid
from collections.abc import Callable, Generator
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

import pytest

from src.application.contracts import AppBoardSummary
from src.application.shared.readiness import ReadinessProbe
from src.domain.kanban.models import Board, Card, CardPriority, Column
from src.domain.shared.errors import KanbanError
from src.domain.shared.result import Err, Ok, Result
from src.infrastructure.persistence.in_memory_repository import InMemoryKanbanRepository
from src.infrastructure.persistence.lifecycle import ClosableResource
from src.infrastructure.persistence.sqlmodel_repository import SQLiteKanbanRepository

pytestmark = pytest.mark.unit


class RepositoryContract(Protocol):
    def save(self, board: Board) -> None: ...

    def list_all(self) -> list[AppBoardSummary]: ...

    def find_by_id(self, board_id: str) -> Result[Board, KanbanError]: ...

    def remove(self, board_id: str) -> Result[None, KanbanError]: ...

    def find_board_id_by_card(self, card_id: str) -> str | None: ...

    def find_board_id_by_column(self, column_id: str) -> str | None: ...


def _new_board(title: str) -> Board:
    return Board(
        id=str(uuid.uuid4()),
        title=title,
        created_at=datetime.now(),
        columns=[],
    )


def _find_card(board: Board, card_id: str) -> Card | None:
    for column in board.columns:
        for card in column.cards:
            if card.id == card_id:
                return card
    return None


def _append_column(
    repository: RepositoryContract,
    board_id: str,
    title: str,
) -> Result[Column, KanbanError]:
    board_result = repository.find_by_id(board_id)
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
    repository.save(board)
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

    board_result = repository.find_by_id(board_id)
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
    repository.save(board)
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
    response = repo.find_by_id("00000000-0000-4000-8000-000000000001")
    assert isinstance(response, Err)
    assert response.error is KanbanError.BOARD_NOT_FOUND


def test_repository_contract_lists_created_boards(
    repository_factory: Callable[[], RepositoryContract],
) -> None:
    repo = repository_factory()
    created = _new_board("Sprint")
    repo.save(created)

    listed = repo.list_all()
    assert {board.id for board in listed} == {created.id}


def test_repository_contract_remove_deletes_board_and_nested_lookups(
    repository_factory: Callable[[], RepositoryContract],
) -> None:
    repo = repository_factory()
    board = _new_board("With children")
    repo.save(board)

    column_result = _append_column(repo, board.id, "Column")
    assert isinstance(column_result, Ok)
    card_result = _append_card(repo, column_result.value.id, "Task", None)
    assert isinstance(card_result, Ok)

    removed = repo.remove(board.id)
    assert isinstance(removed, Ok)
    assert isinstance(repo.find_by_id(board.id), Err)
    assert repo.find_board_id_by_column(column_result.value.id) is None
    assert repo.find_board_id_by_card(card_result.value.id) is None


def test_repository_contract_persists_card_sequence(
    repository_factory: Callable[[], RepositoryContract],
) -> None:
    """Verify that adapters persist card ordering updates."""
    repo = repository_factory()
    board = _new_board("Seq")
    repo.save(board)
    col = _append_column(repo, board.id, "C")
    assert isinstance(col, Ok)
    c1 = _append_card(repo, col.value.id, "a", None)
    c2 = _append_card(repo, col.value.id, "b", None)
    assert isinstance(c1, Ok) and isinstance(c2, Ok)

    board_result = repo.find_by_id(board.id)
    assert isinstance(board_result, Ok)
    move_error = board_result.value.move_card(
        c1.value.id,
        source_column_id=col.value.id,
        target_column_id=col.value.id,
        requested_position=1,
    )
    assert move_error is None
    repo.save(board_result.value)

    board_r = repo.find_by_id(board.id)
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
    board = _new_board("A")
    repo.save(board)
    col = _append_column(repo, board.id, "C")
    assert isinstance(col, Ok)
    assert repo.find_board_id_by_column(col.value.id) == board.id
    assert repo.find_board_id_by_column("nonexistent") is None


def test_repository_contract_persists_priority_and_due_at(
    repository_factory: Callable[[], RepositoryContract],
) -> None:
    repo = repository_factory()
    board = _new_board("Priority+Due")
    repo.save(board)
    column_result = _append_column(repo, board.id, "Todo")
    assert isinstance(column_result, Ok)

    due_at = datetime(2033, 4, 4, 12, 0, tzinfo=timezone.utc)
    card_result = _append_card(
        repo,
        column_result.value.id,
        "Task",
        "Note",
        priority=CardPriority.HIGH,
        due_at=due_at,
    )
    assert isinstance(card_result, Ok)

    board_result = repo.find_by_id(board.id)
    assert isinstance(board_result, Ok)
    nested = _find_card(board_result.value, card_result.value.id)
    assert nested is not None
    assert nested.priority is CardPriority.HIGH
    assert nested.due_at == due_at


def test_repository_contract_persists_saved_card_field_updates(
    repository_factory: Callable[[], RepositoryContract],
) -> None:
    repo = repository_factory()
    board = _new_board("Card updates")
    repo.save(board)
    column_result = _append_column(repo, board.id, "Todo")
    assert isinstance(column_result, Ok)
    card_result = _append_card(repo, column_result.value.id, "old", "desc")
    assert isinstance(card_result, Ok)

    loaded = repo.find_by_id(board.id)
    assert isinstance(loaded, Ok)
    card = _find_card(loaded.value, card_result.value.id)
    assert card is not None
    card.title = "new"
    card.priority = CardPriority.LOW
    card.due_at = datetime(2031, 2, 2, 0, 0, tzinfo=timezone.utc)
    repo.save(loaded.value)

    refreshed = repo.find_by_id(board.id)
    assert isinstance(refreshed, Ok)
    updated = _find_card(refreshed.value, card_result.value.id)
    assert updated is not None
    assert updated.title == "new"
    assert updated.priority is CardPriority.LOW
    assert updated.due_at == datetime(2031, 2, 2, 0, 0, tzinfo=timezone.utc)


def test_sqlite_repository_persists_data_across_instances(tmp_path: Path) -> None:
    db_path = tmp_path / "kanban-persist.sqlite3"
    first = SQLiteKanbanRepository(str(db_path))
    created = _new_board("Persistent")
    first.save(created)
    second = SQLiteKanbanRepository(str(db_path))
    boards = second.list_all()
    assert any(board.id == created.id for board in boards)
    first.close()
    second.close()


def test_repository_implementations_conform_to_protocol(tmp_path: Path) -> None:
    sqlite_repo = SQLiteKanbanRepository(str(tmp_path / "repo-protocol.sqlite3"))
    in_memory_repo = InMemoryKanbanRepository()

    typed_sqlite: RepositoryContract = sqlite_repo
    typed_in_memory: RepositoryContract = in_memory_repo

    created_sqlite = _new_board("contract-sqlite")
    typed_sqlite.save(created_sqlite)
    assert created_sqlite.id
    assert any(board.id == created_sqlite.id for board in typed_sqlite.list_all())

    created_inmemory = _new_board("contract")
    typed_in_memory.save(created_inmemory)
    assert created_inmemory.id
    assert any(
        board.id == created_inmemory.id for board in typed_in_memory.list_all()
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
        board = _new_board("ctx")
        repository.save(board)
        assert board.id
    assert repository.is_ready() is False
