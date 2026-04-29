from __future__ import annotations

import uuid
from collections.abc import Callable, Generator
from datetime import datetime, timezone
from typing import Protocol

import pytest

from src.application.shared.readiness import ReadinessProbe
from src.domain.kanban.errors import KanbanError
from src.domain.kanban.models import Board, BoardSummary, Card, CardPriority, Column
from src.domain.shared.result import Err, Ok, Result
from src.infrastructure.adapters.outbound.persistence.lifecycle import ClosableResource
from src.infrastructure.adapters.outbound.persistence.sqlmodel.repository import (
    PersistenceConflictError,
    SQLModelKanbanRepository,
)

pytestmark = pytest.mark.unit


class RepositoryContract(Protocol):
    def save(self, board: Board) -> None: ...

    def list_all(self) -> list[BoardSummary]: ...

    def find_by_id(self, board_id: str) -> Result[Board, KanbanError]: ...

    def find_card_by_id(self, card_id: str) -> Result[Card, KanbanError]: ...

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
    board.add_column(column)
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


@pytest.fixture
def repository_factory(
    postgresql_dsn: str,
) -> Generator[Callable[[], RepositoryContract], None, None]:
    created_repositories: list[RepositoryContract] = []

    def make_postgresql() -> RepositoryContract:
        repository = SQLModelKanbanRepository(postgresql_dsn)
        created_repositories.append(repository)
        return repository

    yield make_postgresql

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
    board_result.value.move_card(
        c1.value.id,
        source_column_id=col.value.id,
        target_column_id=col.value.id,
        requested_position=1,
    )
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


def test_repository_contract_rejects_stale_board_version(
    repository_factory: Callable[[], RepositoryContract],
) -> None:
    repo_a = repository_factory()
    repo_b = repository_factory()
    board = _new_board("Concurrency")
    repo_a.save(board)

    loaded_a = repo_a.find_by_id(board.id)
    loaded_b = repo_b.find_by_id(board.id)
    assert isinstance(loaded_a, Ok)
    assert isinstance(loaded_b, Ok)

    loaded_a.value.rename("A")
    repo_a.save(loaded_a.value)

    loaded_b.value.rename("B")
    with pytest.raises(PersistenceConflictError):
        repo_b.save(loaded_b.value)


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


def test_repository_contract_find_card_by_id(
    repository_factory: Callable[[], RepositoryContract],
) -> None:
    repo = repository_factory()
    board = _new_board("Cards")
    repo.save(board)
    column_result = _append_column(repo, board.id, "Todo")
    assert isinstance(column_result, Ok)
    card_result = _append_card(repo, column_result.value.id, "Task", None)
    assert isinstance(card_result, Ok)

    fetched = repo.find_card_by_id(card_result.value.id)
    assert isinstance(fetched, Ok)
    assert fetched.value.id == card_result.value.id
    assert fetched.value.title == "Task"

    missing = repo.find_card_by_id("00000000-0000-4000-8000-000000000099")
    assert isinstance(missing, Err)
    assert missing.error is KanbanError.CARD_NOT_FOUND


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


def test_repository_persists_data_across_instances(postgresql_dsn: str) -> None:
    first = SQLModelKanbanRepository(postgresql_dsn)
    created = _new_board("Persistent")
    first.save(created)
    second = SQLModelKanbanRepository(postgresql_dsn)
    boards = second.list_all()
    assert any(board.id == created.id for board in boards)
    first.close()
    second.close()


def test_repository_implementations_conform_to_protocol(postgresql_dsn: str) -> None:
    repository = SQLModelKanbanRepository(postgresql_dsn)

    typed_repository: RepositoryContract = repository

    created = _new_board("contract-postgresql")
    typed_repository.save(created)
    assert created.id
    assert any(board.id == created.id for board in typed_repository.list_all())

    probe: ReadinessProbe = repository
    assert probe.is_ready() is True

    lifecycle: ClosableResource = repository
    lifecycle.close()


def test_repository_close_is_idempotent(postgresql_dsn: str) -> None:
    repository = SQLModelKanbanRepository(postgresql_dsn)
    lifecycle: ClosableResource = repository
    probe: ReadinessProbe = repository
    lifecycle.close()
    lifecycle.close()
    assert probe.is_ready() is False


def test_repository_context_manager_closes_connection(postgresql_dsn: str) -> None:
    with SQLModelKanbanRepository(postgresql_dsn) as repository:
        board = _new_board("ctx")
        repository.save(board)
        assert board.id
    assert repository.is_ready() is False
