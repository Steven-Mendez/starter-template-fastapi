"""Unit tests for Kanban application create board use case behavior."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from src.features.authorization.application.types import Relationship
from src.features.kanban.application.commands import CreateBoardCommand
from src.features.kanban.application.use_cases.board import CreateBoardUseCase
from src.features.kanban.tests.fakes import (
    FakeKanbanWiring,
    InMemoryKanbanRepository,
)
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


class _RecordingAuthorization:
    """Recording authorization that lets tests assert tuple writes happened."""

    def __init__(self) -> None:
        self.writes: list[Relationship] = []

    def write_relationships(self, tuples: list[Relationship]) -> None:
        self.writes.extend(tuples)

    # Stubs for protocol compliance
    def check(self, **_: object) -> bool:  # pragma: no cover
        return True

    def lookup_resources(self, **_: object) -> list[str]:  # pragma: no cover
        return []

    def lookup_subjects(self, **_: object) -> list[UUID]:  # pragma: no cover
        return []

    def delete_relationships(self, *_: object) -> None:  # pragma: no cover
        return None


class _RaisingAuthorization(_RecordingAuthorization):
    """Authorization fake that simulates a write failure."""

    def write_relationships(self, tuples: list[Relationship]) -> None:
        raise RuntimeError("simulated relationship-store outage")


def test_create_writes_initial_owner_tuple(
    repository: InMemoryKanbanRepository,
    wiring: FakeKanbanWiring,
) -> None:
    """Successful creation grants the actor the ``owner`` relation."""
    from src.features.kanban.tests.fakes import (
        build_fake_kanban_wiring,  # noqa: PLC0415
    )

    authz = _RecordingAuthorization()
    wiring = build_fake_kanban_wiring(repository=repository, authorization=authz)
    actor = uuid4()
    use_case = CreateBoardUseCase(
        uow=wiring.uow_factory(), id_gen=wiring.id_gen, clock=wiring.clock
    )

    result = use_case.execute(CreateBoardCommand(title="Owned", actor_id=actor))

    assert isinstance(result, Ok)
    assert len(authz.writes) == 1
    written = authz.writes[0]
    assert written.resource_type == "kanban"
    assert written.resource_id == result.value.id
    assert written.relation == "owner"
    assert written.subject_id == str(actor)


def test_create_skips_owner_tuple_when_actor_is_anonymous(
    repository: InMemoryKanbanRepository,
    wiring: FakeKanbanWiring,
) -> None:
    """Without an actor there is nobody to own the board — no tuple is written."""
    from src.features.kanban.tests.fakes import (
        build_fake_kanban_wiring,  # noqa: PLC0415
    )

    authz = _RecordingAuthorization()
    wiring = build_fake_kanban_wiring(repository=repository, authorization=authz)
    use_case = CreateBoardUseCase(
        uow=wiring.uow_factory(), id_gen=wiring.id_gen, clock=wiring.clock
    )

    result = use_case.execute(CreateBoardCommand(title="Anon", actor_id=None))

    assert isinstance(result, Ok)
    assert authz.writes == []


def test_relationship_write_failure_rolls_back_the_board_insert(
    repository: InMemoryKanbanRepository,
    wiring: FakeKanbanWiring,
) -> None:
    """A failure during the owner-tuple write must not leave a half-created board."""
    from src.features.kanban.tests.fakes import (
        build_fake_kanban_wiring,  # noqa: PLC0415
    )

    authz = _RaisingAuthorization()
    wiring = build_fake_kanban_wiring(repository=repository, authorization=authz)
    actor = uuid4()
    use_case = CreateBoardUseCase(
        uow=wiring.uow_factory(), id_gen=wiring.id_gen, clock=wiring.clock
    )

    with pytest.raises(RuntimeError, match="simulated"):
        use_case.execute(CreateBoardCommand(title="Doomed", actor_id=actor))

    assert wiring.uow_factory.total_commits == 0
    assert wiring.uow_factory.total_rollbacks >= 1
