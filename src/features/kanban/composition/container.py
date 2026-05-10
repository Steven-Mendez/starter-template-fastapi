"""Composition root for the Kanban feature.

Builds a :class:`KanbanContainer` that exposes use-case factories so
each request gets a fresh unit-of-work without rebuilding repositories
or shared adapters every time.

The container takes an ``AuthorizationPort`` from the auth feature so
kanban use cases can write the initial owner tuple on board creation
and filter listings to a user's accessible boards. The port is the only
auth dependency exposed here — use cases never see relationship tuples
for resources they don't own.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy.engine import Engine  # noqa: F401  (used in Protocol)

from src.features.auth.application.authorization.ports import AuthorizationPort
from src.features.auth.application.authorization.resource_graph import ParentResolver
from src.features.kanban.adapters.outbound.persistence import SQLModelKanbanRepository
from src.features.kanban.adapters.outbound.persistence.sqlmodel.unit_of_work import (
    SqlModelUnitOfWork,
)
from src.features.kanban.adapters.outbound.query.kanban_query_repository_view import (
    KanbanQueryRepositoryView,
)
from src.features.kanban.application.ports.inbound import (
    CheckReadinessUseCasePort,
    CreateBoardUseCasePort,
    CreateCardUseCasePort,
    CreateColumnUseCasePort,
    DeleteBoardUseCasePort,
    DeleteColumnUseCasePort,
    GetBoardUseCasePort,
    GetCardUseCasePort,
    ListBoardsUseCasePort,
    PatchBoardUseCasePort,
    PatchCardUseCasePort,
    RestoreBoardUseCasePort,
)
from src.features.kanban.application.ports.outbound import (
    KanbanCommandRepositoryPort,
    KanbanLookupRepositoryPort,
    KanbanQueryRepositoryPort,
    UnitOfWorkPort,
)
from src.features.kanban.application.use_cases.board import (
    CreateBoardUseCase,
    DeleteBoardUseCase,
    GetBoardUseCase,
    ListBoardsUseCase,
    PatchBoardUseCase,
    RestoreBoardUseCase,
)
from src.features.kanban.application.use_cases.card import (
    CreateCardUseCase,
    GetCardUseCase,
    PatchCardUseCase,
)
from src.features.kanban.application.use_cases.column import (
    CreateColumnUseCase,
    DeleteColumnUseCase,
)
from src.features.kanban.application.use_cases.health.check_readiness import (
    CheckReadinessUseCase,
)
from src.platform.persistence.readiness import ReadinessProbe
from src.platform.shared.adapters.system_clock import SystemClock
from src.platform.shared.adapters.uuid_id_generator import UUIDIdGenerator
from src.platform.shared.clock_port import ClockPort
from src.platform.shared.id_generator_port import IdGeneratorPort

UnitOfWorkFactory = Callable[[], UnitOfWorkPort]


class _ManagedKanbanRepository(
    KanbanCommandRepositoryPort,
    KanbanLookupRepositoryPort,
    KanbanQueryRepositoryPort,
    ReadinessProbe,
    Protocol,
):
    """Shape every "owned" repository must satisfy: ports + ``engine`` + ``close``."""

    @property
    def engine(self) -> Engine: ...

    def close(self) -> None: ...


class _LookupParentResolver:
    """Adapt the kanban lookup repository to the ``ParentResolver`` Protocol."""

    def __init__(self, lookup: KanbanLookupRepositoryPort) -> None:
        self._lookup = lookup

    def board_id_for_card(self, card_id: str) -> str | None:
        return self._lookup.find_board_id_by_card(card_id)

    def board_id_for_column(self, column_id: str) -> str | None:
        return self._lookup.find_board_id_by_column(column_id)


@dataclass(slots=True)
class KanbanContainer:
    """Holds shared adapters and produces fresh use-case instances per request."""

    query_repository: KanbanQueryRepositoryPort
    uow_factory: UnitOfWorkFactory
    authorization: AuthorizationPort
    parent_resolver: ParentResolver
    id_gen: IdGeneratorPort
    clock: ClockPort
    readiness_probe: ReadinessProbe
    shutdown: Callable[[], None]

    def create_board_use_case(self) -> CreateBoardUseCasePort:
        return CreateBoardUseCase(
            uow=self.uow_factory(), id_gen=self.id_gen, clock=self.clock
        )

    def patch_board_use_case(self) -> PatchBoardUseCasePort:
        return PatchBoardUseCase(uow=self.uow_factory())

    def delete_board_use_case(self) -> DeleteBoardUseCasePort:
        return DeleteBoardUseCase(uow=self.uow_factory())

    def restore_board_use_case(self) -> RestoreBoardUseCasePort:
        return RestoreBoardUseCase(uow=self.uow_factory())

    def get_board_use_case(self) -> GetBoardUseCasePort:
        return GetBoardUseCase(query_repository=self.query_repository)

    def list_boards_use_case(self) -> ListBoardsUseCasePort:
        return ListBoardsUseCase(
            query_repository=self.query_repository,
            authorization=self.authorization,
        )

    def create_column_use_case(self) -> CreateColumnUseCasePort:
        return CreateColumnUseCase(uow=self.uow_factory(), id_gen=self.id_gen)

    def delete_column_use_case(self) -> DeleteColumnUseCasePort:
        return DeleteColumnUseCase(uow=self.uow_factory())

    def create_card_use_case(self) -> CreateCardUseCasePort:
        return CreateCardUseCase(uow=self.uow_factory(), id_gen=self.id_gen)

    def patch_card_use_case(self) -> PatchCardUseCasePort:
        return PatchCardUseCase(uow=self.uow_factory())

    def get_card_use_case(self) -> GetCardUseCasePort:
        return GetCardUseCase(query_repository=self.query_repository)

    def check_readiness_use_case(self) -> CheckReadinessUseCasePort:
        return CheckReadinessUseCase(readiness=self.readiness_probe)


def build_kanban_container(
    *,
    authorization: AuthorizationPort,
    postgresql_dsn: str | None = None,
    repository: _ManagedKanbanRepository | None = None,
    pool_size: int = 5,
    max_overflow: int = 10,
    pool_recycle: int = 1800,
    pool_pre_ping: bool = True,
) -> KanbanContainer:
    """Wire the Kanban container.

    Args:
        authorization: The auth feature's ``AuthorizationPort``. Reused for
            list filtering; a session-scoped variant is constructed per
            unit-of-work for transactional writes (see ``SqlModelUnitOfWork``).
        postgresql_dsn: Production DSN for the kanban database.
        repository: Optional pre-built repository for tests.

    The container resolves the parent walk for cross-resource authorization
    via the kanban lookup repository, so card/column checks performed inside
    a unit of work can navigate to the owning board without extra wiring.
    """
    if repository is None:
        if postgresql_dsn is None:
            raise ValueError("Provide either postgresql_dsn or repository")
        repo: _ManagedKanbanRepository = SQLModelKanbanRepository(
            postgresql_dsn,
            create_schema=False,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_recycle=pool_recycle,
            pool_pre_ping=pool_pre_ping,
        )
    else:
        repo = repository

    query_repo = KanbanQueryRepositoryView(repo)
    parent_resolver: ParentResolver = _LookupParentResolver(repo)
    return KanbanContainer(
        query_repository=query_repo,
        uow_factory=lambda: SqlModelUnitOfWork(
            repo.engine, parent_resolver=parent_resolver
        ),
        authorization=authorization,
        parent_resolver=parent_resolver,
        id_gen=UUIDIdGenerator(),
        clock=SystemClock(),
        readiness_probe=repo,
        shutdown=repo.close,
    )
