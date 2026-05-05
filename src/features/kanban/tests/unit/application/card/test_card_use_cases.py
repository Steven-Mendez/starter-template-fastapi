from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.features.kanban.application.commands import (
    CreateBoardCommand,
    CreateCardCommand,
    CreateColumnCommand,
    PatchCardCommand,
)
from src.features.kanban.application.contracts import AppCardPriority
from src.features.kanban.application.errors import ApplicationError
from src.features.kanban.application.queries import GetCardQuery
from src.features.kanban.application.use_cases.board import CreateBoardUseCase
from src.features.kanban.application.use_cases.card import (
    CreateCardUseCase,
    GetCardUseCase,
    PatchCardUseCase,
)
from src.features.kanban.application.use_cases.column import CreateColumnUseCase
from src.features.kanban.tests.fakes import FakeKanbanWiring
from src.platform.shared.result import Err, Ok

pytestmark = pytest.mark.unit


def _seed_board_and_column(wiring: FakeKanbanWiring) -> tuple[str, str]:
    board = CreateBoardUseCase(
        uow=wiring.uow_factory(), id_gen=wiring.id_gen, clock=wiring.clock
    ).execute(CreateBoardCommand(title="b"))
    assert isinstance(board, Ok)
    column = CreateColumnUseCase(
        uow=wiring.uow_factory(), id_gen=wiring.id_gen
    ).execute(CreateColumnCommand(board_id=board.value.id, title="todo"))
    assert isinstance(column, Ok)
    return board.value.id, column.value.id


def test_create_card_succeeds(wiring: FakeKanbanWiring) -> None:
    _, column_id = _seed_board_and_column(wiring)
    use_case = CreateCardUseCase(uow=wiring.uow_factory(), id_gen=wiring.id_gen)
    result = use_case.execute(
        CreateCardCommand(
            column_id=column_id,
            title="task",
            description=None,
            priority=AppCardPriority.MEDIUM,
            due_at=None,
        )
    )
    assert isinstance(result, Ok)
    assert result.value.title == "task"


def test_create_card_column_missing(wiring: FakeKanbanWiring) -> None:
    use_case = CreateCardUseCase(uow=wiring.uow_factory(), id_gen=wiring.id_gen)
    result = use_case.execute(
        CreateCardCommand(
            column_id="missing",
            title="t",
            description=None,
            priority=AppCardPriority.LOW,
            due_at=None,
        )
    )
    assert isinstance(result, Err)
    assert result.error == ApplicationError.COLUMN_NOT_FOUND


def test_get_card(wiring: FakeKanbanWiring) -> None:
    _, column_id = _seed_board_and_column(wiring)
    created = CreateCardUseCase(uow=wiring.uow_factory(), id_gen=wiring.id_gen).execute(
        CreateCardCommand(
            column_id=column_id,
            title="t",
            description=None,
            priority=AppCardPriority.LOW,
            due_at=None,
        )
    )
    assert isinstance(created, Ok)
    use_case = GetCardUseCase(query_repository=wiring.container.query_repository)
    result = use_case.execute(GetCardQuery(card_id=created.value.id))
    assert isinstance(result, Ok)
    assert result.value.title == "t"


def test_get_card_missing(wiring: FakeKanbanWiring) -> None:
    use_case = GetCardUseCase(query_repository=wiring.container.query_repository)
    result = use_case.execute(GetCardQuery(card_id="missing"))
    assert isinstance(result, Err)
    assert result.error == ApplicationError.CARD_NOT_FOUND


def test_patch_card_no_changes(wiring: FakeKanbanWiring) -> None:
    use_case = PatchCardUseCase(uow=wiring.uow_factory())
    result = use_case.execute(PatchCardCommand(card_id="any"))
    assert isinstance(result, Err)
    assert result.error == ApplicationError.PATCH_NO_CHANGES


def test_patch_card_renames_and_clears_due_at(wiring: FakeKanbanWiring) -> None:
    _, column_id = _seed_board_and_column(wiring)
    created = CreateCardUseCase(uow=wiring.uow_factory(), id_gen=wiring.id_gen).execute(
        CreateCardCommand(
            column_id=column_id,
            title="t",
            description=None,
            priority=AppCardPriority.LOW,
            due_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
    )
    assert isinstance(created, Ok)

    use_case = PatchCardUseCase(uow=wiring.uow_factory())
    result = use_case.execute(
        PatchCardCommand(card_id=created.value.id, title="renamed", clear_due_at=True)
    )
    assert isinstance(result, Ok)
    assert result.value.title == "renamed"
    assert result.value.due_at is None


def test_patch_card_missing(wiring: FakeKanbanWiring) -> None:
    use_case = PatchCardUseCase(uow=wiring.uow_factory())
    result = use_case.execute(PatchCardCommand(card_id="missing", title="x"))
    assert isinstance(result, Err)
    assert result.error == ApplicationError.CARD_NOT_FOUND
