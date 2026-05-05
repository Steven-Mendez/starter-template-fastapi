from __future__ import annotations

from dataclasses import dataclass

from src.features.kanban.composition.container import KanbanContainer
from src.features.kanban.tests.fakes.fixed_clock import FixedClock
from src.features.kanban.tests.fakes.in_memory_repository import (
    InMemoryKanbanRepository,
)
from src.features.kanban.tests.fakes.in_memory_uow import RecordingUnitOfWorkFactory
from src.features.kanban.tests.fakes.sequential_id_generator import (
    SequentialIdGenerator,
)


@dataclass(slots=True)
class FakeKanbanWiring:
    """Bundle of a real ``KanbanContainer`` plus its in-memory fakes for tests."""

    container: KanbanContainer
    repository: InMemoryKanbanRepository
    uow_factory: RecordingUnitOfWorkFactory
    id_gen: SequentialIdGenerator
    clock: FixedClock


def build_fake_kanban_wiring(
    repository: InMemoryKanbanRepository | None = None,
    *,
    id_prefix: str = "id",
) -> FakeKanbanWiring:
    """Wire a Kanban container against in-memory fakes for tests."""
    repo = repository or InMemoryKanbanRepository()
    uow_factory = RecordingUnitOfWorkFactory(repo)
    id_gen = SequentialIdGenerator(prefix=id_prefix)
    clock = FixedClock()

    container = KanbanContainer(
        query_repository=repo,
        uow_factory=uow_factory,
        id_gen=id_gen,
        clock=clock,
        readiness_probe=repo,
        shutdown=repo.close,
    )
    return FakeKanbanWiring(
        container=container,
        repository=repo,
        uow_factory=uow_factory,
        id_gen=id_gen,
        clock=clock,
    )
