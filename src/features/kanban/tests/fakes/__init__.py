"""Test package namespace for features.kanban.tests.fakes."""

from src.features.kanban.tests.fakes.fake_container import (
    FakeKanbanWiring,
    build_fake_kanban_wiring,
)
from src.features.kanban.tests.fakes.fixed_clock import FixedClock
from src.features.kanban.tests.fakes.in_memory_repository import (
    InMemoryKanbanRepository,
)
from src.features.kanban.tests.fakes.in_memory_uow import (
    InMemoryUnitOfWork,
    RecordingUnitOfWorkFactory,
)
from src.features.kanban.tests.fakes.sequential_id_generator import (
    SequentialIdGenerator,
)

__all__ = [
    "FakeKanbanWiring",
    "FixedClock",
    "InMemoryKanbanRepository",
    "InMemoryUnitOfWork",
    "RecordingUnitOfWorkFactory",
    "SequentialIdGenerator",
    "build_fake_kanban_wiring",
]
