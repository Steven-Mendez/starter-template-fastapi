"""Composition root for the Kanban feature.

Builds a :class:`KanbanContainer` that exposes use-case factories so
each request gets a fresh unit-of-work without rebuilding repositories
or shared adapters every time.

The container takes an ``AuthorizationPort`` from the auth feature so
kanban use cases can write the initial owner tuple on board creation
and filter listings to a user's accessible boards. The port is the only
auth dependency exposed here — use cases never see relationship tuples
for resources they don't own. The authorization registry is the second
seam: kanban registers its resource types into it at composition time
so the engine knows how to walk ``card → column → board`` without any
auth-side knowledge of kanban.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy.engine import Engine  # noqa: F401  (used in Protocol)

from src.features.authorization.application.ports.authorization_port import (
    AuthorizationPort,
)
from src.features.authorization.application.registry import AuthorizationRegistry
from src.features.kanban.adapters.outbound.persistence import SQLModelKanbanRepository
from src.features.kanban.adapters.outbound.persistence.sqlmodel.unit_of_work import (
    SqlModelUnitOfWork,
    UserAuthzVersionFactory,
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


@dataclass(slots=True)
class KanbanContainer:
    """Holds shared adapters and produces fresh use-case instances per request."""

    query_repository: KanbanQueryRepositoryPort
    uow_factory: UnitOfWorkFactory
    authorization: AuthorizationPort
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
    registry: AuthorizationRegistry,
    user_authz_version_factory: UserAuthzVersionFactory,
    postgresql_dsn: str | None = None,
    repository: _ManagedKanbanRepository | None = None,
    pool_size: int = 5,
    max_overflow: int = 10,
    pool_recycle: int = 1800,
    pool_pre_ping: bool = True,
) -> KanbanContainer:
    """Wire the Kanban container.

    Args:
        authorization: The authorization feature's ``AuthorizationPort``.
            Reused for list filtering; a session-scoped variant is
            constructed per unit-of-work for transactional writes (see
            ``SqlModelUnitOfWork``).
        registry: The authorization feature's ``AuthorizationRegistry``.
            Kanban contributes its resource types, hierarchy, and
            parent-walk callables here at construction time so card and
            column checks can navigate to the owning board.
        user_authz_version_factory: Factory the UoW uses to build a
            session-bound ``UserAuthzVersionPort`` so the
            authz_version bump commits or rolls back atomically with
            kanban writes. Kanban never imports auth-side adapter code;
            the factory closure is wired in by ``main.py``.
        postgresql_dsn: Production DSN for the kanban database.
        repository: Optional pre-built repository for tests.
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

    # Local import: ``wiring`` imports ``KanbanContainer`` for HTTP-mount
    # helpers, so the registration helper lives there. Importing it at
    # module top-level would create a cycle.
    from src.features.kanban.composition.wiring import (  # noqa: PLC0415
        register_kanban_authorization,
    )

    register_kanban_authorization(registry, repo)

    query_repo = KanbanQueryRepositoryView(repo)
    return KanbanContainer(
        query_repository=query_repo,
        uow_factory=lambda: SqlModelUnitOfWork(
            repo.engine,
            registry=registry,
            user_authz_version_factory=user_authz_version_factory,
        ),
        authorization=authorization,
        id_gen=UUIDIdGenerator(),
        clock=SystemClock(),
        readiness_probe=repo,
        shutdown=repo.close,
    )
