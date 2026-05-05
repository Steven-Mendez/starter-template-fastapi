from __future__ import annotations

import pytest

from src.features.kanban.application.commands import CreateBoardCommand
from src.features.kanban.application.use_cases.board import CreateBoardUseCase
from src.features.kanban.tests.fakes import FakeKanbanWiring
from src.platform.shared.result import Ok

pytestmark = pytest.mark.unit


def test_creates_board_and_commits(wiring: FakeKanbanWiring) -> None:
    use_case = CreateBoardUseCase(
        uow=wiring.uow_factory(), id_gen=wiring.id_gen, clock=wiring.clock
    )

    result = use_case.execute(CreateBoardCommand(title="Roadmap"))

    assert isinstance(result, Ok)
    assert result.value.title == "Roadmap"
    assert result.value.created_at == wiring.clock.fixed
    assert wiring.uow_factory.total_commits == 1
    assert wiring.repository.list_all()[0].title == "Roadmap"


def test_creates_distinct_boards_with_sequential_ids(wiring: FakeKanbanWiring) -> None:
    use_case = CreateBoardUseCase(
        uow=wiring.uow_factory(), id_gen=wiring.id_gen, clock=wiring.clock
    )
    use_case2 = CreateBoardUseCase(
        uow=wiring.uow_factory(), id_gen=wiring.id_gen, clock=wiring.clock
    )

    a = use_case.execute(CreateBoardCommand(title="A"))
    b = use_case2.execute(CreateBoardCommand(title="B"))

    assert isinstance(a, Ok) and isinstance(b, Ok)
    assert a.value.id != b.value.id
