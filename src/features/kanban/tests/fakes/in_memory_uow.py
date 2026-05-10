"""In-memory unit-of-work and recording factory used by application-layer tests."""

from __future__ import annotations

from types import TracebackType
from typing import Self
from uuid import UUID

from src.features.auth.application.authorization.ports import (
    LOOKUP_DEFAULT_LIMIT,
    AuthorizationPort,
)
from src.features.auth.application.authorization.types import Relationship
from src.features.kanban.application.ports.outbound import (
    KanbanCommandRepositoryPort,
    KanbanLookupRepositoryPort,
    UnitOfWorkPort,
)
from src.features.kanban.tests.fakes.in_memory_repository import (
    InMemoryKanbanRepository,
)


class _NoopAuthorization:
    """Default no-op authorization adapter used when tests don't care about authz."""

    def check(
        self,
        *,
        user_id: UUID,
        action: str,
        resource_type: str,
        resource_id: str,
    ) -> bool:
        return True

    def lookup_resources(
        self,
        *,
        user_id: UUID,
        action: str,
        resource_type: str,
        limit: int = LOOKUP_DEFAULT_LIMIT,
    ) -> list[str]:
        return []

    def lookup_subjects(
        self,
        *,
        resource_type: str,
        resource_id: str,
        relation: str,
    ) -> list[UUID]:
        return []

    def write_relationships(self, tuples: list[Relationship]) -> None:
        return None

    def delete_relationships(self, tuples: list[Relationship]) -> None:
        return None


class InMemoryUnitOfWork(UnitOfWorkPort):
    """In-memory UoW backed by the same repository for read and write."""

    commands: KanbanCommandRepositoryPort
    lookup: KanbanLookupRepositoryPort
    authorization: AuthorizationPort

    def __init__(
        self,
        repository: InMemoryKanbanRepository,
        *,
        authorization: AuthorizationPort | None = None,
    ) -> None:
        """Wire the unit-of-work to a shared in-memory repository."""
        self._repository = repository
        self.commands = repository
        self.lookup = repository
        self.authorization = authorization or _NoopAuthorization()
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

    def __init__(
        self,
        repository: InMemoryKanbanRepository,
        *,
        authorization: AuthorizationPort | None = None,
    ) -> None:
        """Bind the factory to the shared in-memory repository."""
        self._repository = repository
        self._authorization = authorization
        self.created: list[InMemoryUnitOfWork] = []

    def __call__(self) -> InMemoryUnitOfWork:
        """Build and remember a new :class:`InMemoryUnitOfWork`."""
        uow = InMemoryUnitOfWork(self._repository, authorization=self._authorization)
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
