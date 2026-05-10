"""Helpers that wire a real :class:`KanbanContainer` against in-memory fakes."""

from __future__ import annotations

from dataclasses import dataclass

from src.features.auth.application.authorization.ports import AuthorizationPort
from src.features.auth.application.authorization.resource_graph import ParentResolver
from src.features.kanban.composition.container import KanbanContainer
from src.features.kanban.tests.fakes.fixed_clock import FixedClock
from src.features.kanban.tests.fakes.in_memory_repository import (
    InMemoryKanbanRepository,
)
from src.features.kanban.tests.fakes.in_memory_uow import (
    RecordingUnitOfWorkFactory,
    _NoopAuthorization,
)
from src.features.kanban.tests.fakes.sequential_id_generator import (
    SequentialIdGenerator,
)


class _RepoParentResolver:
    """Walk parents via the in-memory kanban repository."""

    def __init__(self, repo: InMemoryKanbanRepository) -> None:
        self._repo = repo

    def board_id_for_card(self, card_id: str) -> str | None:
        return self._repo.find_board_id_by_card(card_id)

    def board_id_for_column(self, column_id: str) -> str | None:
        return self._repo.find_board_id_by_column(column_id)


@dataclass(slots=True)
class FakeKanbanWiring:
    """Bundle of a real ``KanbanContainer`` plus its in-memory fakes for tests."""

    container: KanbanContainer
    repository: InMemoryKanbanRepository
    uow_factory: RecordingUnitOfWorkFactory
    id_gen: SequentialIdGenerator
    clock: FixedClock
    authorization: AuthorizationPort


def build_fake_kanban_wiring(
    repository: InMemoryKanbanRepository | None = None,
    *,
    authorization: AuthorizationPort | None = None,
    id_prefix: str = "id",
) -> FakeKanbanWiring:
    """Wire a Kanban container against in-memory fakes for tests."""
    repo = repository or InMemoryKanbanRepository()
    auth: AuthorizationPort = authorization or _NoopAuthorization()
    uow_factory = RecordingUnitOfWorkFactory(repo, authorization=auth)
    id_gen = SequentialIdGenerator(prefix=id_prefix)
    clock = FixedClock()
    parent_resolver: ParentResolver = _RepoParentResolver(repo)

    container = KanbanContainer(
        query_repository=repo,
        uow_factory=uow_factory,
        authorization=auth,
        parent_resolver=parent_resolver,
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
        authorization=auth,
    )
