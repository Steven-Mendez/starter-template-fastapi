from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy.engine import Engine  # noqa: F401  (used in Protocol)

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
    @property
    def engine(self) -> Engine: ...

    def close(self) -> None: ...


@dataclass(slots=True)
class KanbanContainer:
    query_repository: KanbanQueryRepositoryPort
    uow_factory: UnitOfWorkFactory
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

    def get_board_use_case(self) -> GetBoardUseCasePort:
        return GetBoardUseCase(query_repository=self.query_repository)

    def list_boards_use_case(self) -> ListBoardsUseCasePort:
        return ListBoardsUseCase(query_repository=self.query_repository)

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
    postgresql_dsn: str | None = None,
    repository: _ManagedKanbanRepository | None = None,
) -> KanbanContainer:
    """Wire the Kanban container.

    In production, pass ``postgresql_dsn`` and the container manages its own
    engine via ``SQLModelKanbanRepository``. In tests, pass a fake ``repository``
    implementing the managed-repository surface.
    """
    if repository is None:
        if postgresql_dsn is None:
            raise ValueError("Provide either postgresql_dsn or repository")
        repo: _ManagedKanbanRepository = SQLModelKanbanRepository(
            postgresql_dsn, create_schema=False
        )
    else:
        repo = repository

    query_repo = KanbanQueryRepositoryView(repo)
    return KanbanContainer(
        query_repository=query_repo,
        uow_factory=lambda: SqlModelUnitOfWork(repo.engine),
        id_gen=UUIDIdGenerator(),
        clock=SystemClock(),
        readiness_probe=repo,
        shutdown=repo.close,
    )
