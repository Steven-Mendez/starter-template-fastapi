"""In-memory unit-of-work and recording factory used by application-layer tests."""

from __future__ import annotations

from types import TracebackType
from typing import Self

from src.features.kanban.application.ports.outbound import (
    KanbanCommandRepositoryPort,
    KanbanLookupRepositoryPort,
    UnitOfWorkPort,
)
from src.features.kanban.tests.fakes.in_memory_repository import (
    InMemoryKanbanRepository,
)


class InMemoryUnitOfWork(UnitOfWorkPort):
    """In-memory UoW backed by the same repository for read and write.

    The counters and flags expose the unit-of-work's lifecycle to tests
    so they can assert that a use case really committed (or rolled back)
    instead of just running the happy-path code.
    """

    commands: KanbanCommandRepositoryPort
    lookup: KanbanLookupRepositoryPort

    def __init__(self, repository: InMemoryKanbanRepository) -> None:
        """Wire the unit-of-work to a shared in-memory repository."""
        self._repository = repository
        self.commands = repository
        self.lookup = repository
        self.commit_count = 0
        self.rollback_count = 0
        self.entered = False
        self.exited = False

    def __enter__(self) -> Self:
        self.entered = True
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        del exc_val, exc_tb
        self.exited = True
        if exc_type is not None:
            self.rollback_count += 1

    def commit(self) -> None:
        self.commit_count += 1

    def rollback(self) -> None:
        self.rollback_count += 1


class RecordingUnitOfWorkFactory:
    """Factory that records every UoW it creates for transactional assertions."""

    def __init__(self, repository: InMemoryKanbanRepository) -> None:
        """Bind the factory to the shared in-memory repository."""
        self._repository = repository
        self.created: list[InMemoryUnitOfWork] = []

    def __call__(self) -> InMemoryUnitOfWork:
        """Build and remember a new :class:`InMemoryUnitOfWork`."""
        uow = InMemoryUnitOfWork(self._repository)
        self.created.append(uow)
        return uow

    @property
    def total_commits(self) -> int:
        """Sum of commits across every UoW handed out by this factory."""
        return sum(u.commit_count for u in self.created)

    @property
    def total_rollbacks(self) -> int:
        """Sum of rollbacks across every UoW handed out by this factory."""
        return sum(u.rollback_count for u in self.created)
