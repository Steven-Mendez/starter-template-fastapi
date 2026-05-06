"""Composition root for the Kanban feature.

Builds a :class:`KanbanContainer` that exposes use-case factories so
each request gets a fresh unit-of-work without rebuilding repositories
or shared adapters every time.
"""

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
    """Shape every "owned" repository must satisfy: ports + ``engine`` + ``close``.

    The container only knows how to wire something that exposes this
    full surface, which lets either the production
    ``SQLModelKanbanRepository`` or a test fake be plugged in
    interchangeably.
    """

    @property
    def engine(self) -> Engine: ...

    def close(self) -> None: ...


@dataclass(slots=True)
class KanbanContainer:
    """Holds shared adapters and produces fresh use-case instances per request.

    Building use cases lazily through factories means each invocation
    receives its own unit-of-work / session, while the comparatively
    expensive repository, clock, and id generator are reused across the
    whole process.
    """

    query_repository: KanbanQueryRepositoryPort
    uow_factory: UnitOfWorkFactory
    id_gen: IdGeneratorPort
    clock: ClockPort
    readiness_probe: ReadinessProbe
    shutdown: Callable[[], None]

    def create_board_use_case(self) -> CreateBoardUseCasePort:
        """Build a :class:`CreateBoardUseCase` with a fresh unit-of-work."""
        return CreateBoardUseCase(
            uow=self.uow_factory(), id_gen=self.id_gen, clock=self.clock
        )

    def patch_board_use_case(self) -> PatchBoardUseCasePort:
        """Build a :class:`PatchBoardUseCase` with a fresh unit-of-work."""
        return PatchBoardUseCase(uow=self.uow_factory())

    def delete_board_use_case(self) -> DeleteBoardUseCasePort:
        """Build a :class:`DeleteBoardUseCase` with a fresh unit-of-work."""
        return DeleteBoardUseCase(uow=self.uow_factory())

    def get_board_use_case(self) -> GetBoardUseCasePort:
        """Build :class:`GetBoardUseCase` with the shared query repository."""
        return GetBoardUseCase(query_repository=self.query_repository)

    def list_boards_use_case(self) -> ListBoardsUseCasePort:
        """Build :class:`ListBoardsUseCase` with the shared query repository."""
        return ListBoardsUseCase(query_repository=self.query_repository)

    def create_column_use_case(self) -> CreateColumnUseCasePort:
        """Build a :class:`CreateColumnUseCase` with a fresh unit-of-work."""
        return CreateColumnUseCase(uow=self.uow_factory(), id_gen=self.id_gen)

    def delete_column_use_case(self) -> DeleteColumnUseCasePort:
        """Build a :class:`DeleteColumnUseCase` with a fresh unit-of-work."""
        return DeleteColumnUseCase(uow=self.uow_factory())

    def create_card_use_case(self) -> CreateCardUseCasePort:
        """Build a :class:`CreateCardUseCase` with a fresh unit-of-work."""
        return CreateCardUseCase(uow=self.uow_factory(), id_gen=self.id_gen)

    def patch_card_use_case(self) -> PatchCardUseCasePort:
        """Build a :class:`PatchCardUseCase` with a fresh unit-of-work."""
        return PatchCardUseCase(uow=self.uow_factory())

    def get_card_use_case(self) -> GetCardUseCasePort:
        """Build :class:`GetCardUseCase` with the shared query repository."""
        return GetCardUseCase(query_repository=self.query_repository)

    def check_readiness_use_case(self) -> CheckReadinessUseCasePort:
        """Build :class:`CheckReadinessUseCase` using the readiness probe."""
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
