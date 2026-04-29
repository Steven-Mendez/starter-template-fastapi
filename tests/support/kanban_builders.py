from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal, Protocol, TypeVar, cast

from fastapi.testclient import TestClient
from httpx import Response

from src.application.commands import (
    CreateBoardCommand,
    CreateCardCommand,
    CreateColumnCommand,
)
from src.application.commands.card.patch import PatchCardCommand
from src.application.commands.column.delete import DeleteColumnCommand
from src.application.contracts import (
    AppBoardSummary,
    AppCard,
    AppCardPriority,
    AppColumn,
)
from src.application.queries.get_board import GetBoardQuery
from src.application.queries.get_card import GetCardQuery
from src.application.queries.health_check import HealthCheckQuery
from src.application.use_cases.board import (
    CreateBoardUseCase,
    DeleteBoardUseCase,
    GetBoardUseCase,
    ListBoardsUseCase,
    PatchBoardUseCase,
)
from src.application.use_cases.card import (
    CreateCardUseCase,
    GetCardUseCase,
    PatchCardUseCase,
)
from src.application.use_cases.column import CreateColumnUseCase, DeleteColumnUseCase
from src.application.use_cases.health.check_readiness import CheckReadinessUseCase
from src.domain.kanban.errors import KanbanError
from src.domain.kanban.models import (
    Board,
    BoardSummary,
    Card,
    Column,
)
from src.domain.kanban.models import (
    CardPriority as DomainCardPriority,
)
from src.domain.shared.result import Err, Ok, Result, expect_ok
from src.infrastructure.adapters.outbound.persistence.sqlmodel.repository import (
    SQLModelKanbanRepository,
)
from src.infrastructure.adapters.outbound.persistence.sqlmodel.unit_of_work import (
    SqlModelUnitOfWork,
)
from src.infrastructure.adapters.outbound.query.kanban_query_repository_view import (
    KanbanQueryRepositoryView,
)
from tests.support.fakes import FakeClock, FakeIdGenerator

type JsonDict = dict[str, Any]
type PriorityLiteral = Literal["low", "medium", "high"]


class KanbanBuilderRepository(Protocol):
    def save(self, board: Board) -> None: ...

    def list_all(self) -> list[BoardSummary]: ...

    def find_by_id(self, board_id: str) -> Result[Board, KanbanError]: ...

    def remove(self, board_id: str) -> Result[None, KanbanError]: ...

    def find_board_id_by_column(self, column_id: str) -> str | None: ...

    def find_board_id_by_card(self, card_id: str) -> str | None: ...


_T = TypeVar("_T")
_E = TypeVar("_E")


def _expect_app_ok(result: Result[_T, _E]) -> _T:
    match result:
        case Ok(value=v):
            return v
        case Err(error=e):
            raise AssertionError(e)


@dataclass(slots=True)
class StoreBuilder:
    repository: KanbanBuilderRepository

    def board(self, title: str = "Board") -> AppBoardSummary:
        board = Board(
            id=str(uuid.uuid4()),
            title=title,
            created_at=datetime.now(timezone.utc),
            columns=[],
        )
        self.repository.save(board)
        return AppBoardSummary(
            id=board.id,
            title=board.title,
            created_at=board.created_at,
        )

    def _load_board(self, board_id: str) -> Board:
        return expect_ok(self.repository.find_by_id(board_id))

    def column(self, board_id: str, title: str = "Todo") -> Column:
        board = self._load_board(board_id)
        column = Column(
            id=str(uuid.uuid4()),
            board_id=board_id,
            title=title,
            position=max(
                (candidate.position for candidate in board.columns), default=-1
            )
            + 1,
            cards=[],
        )
        board.add_column(column)
        self.repository.save(board)
        return column

    def card(
        self,
        column_id: str,
        title: str = "Task",
        description: str | None = None,
        *,
        priority: DomainCardPriority = DomainCardPriority.MEDIUM,
        due_at: datetime | None = None,
    ) -> Card:
        board_id = self.repository.find_board_id_by_column(column_id)
        if board_id is None:
            raise AssertionError(KanbanError.COLUMN_NOT_FOUND)

        board = self._load_board(board_id)
        column = next(
            (candidate for candidate in board.columns if candidate.id == column_id),
            None,
        )
        if column is None:
            raise AssertionError(KanbanError.COLUMN_NOT_FOUND)

        card = Card(
            id=str(uuid.uuid4()),
            column_id=column_id,
            title=title,
            description=description,
            position=0,
            priority=priority,
            due_at=due_at,
        )
        column.insert_card(card)
        self.repository.save(board)
        return card


@dataclass(slots=True)
class HandlerHarness:
    repository: SQLModelKanbanRepository
    create_board_use_case: CreateBoardUseCase
    patch_board_use_case: PatchBoardUseCase
    delete_board_use_case: DeleteBoardUseCase
    get_board_use_case: GetBoardUseCase
    list_boards_use_case: ListBoardsUseCase
    create_column_use_case: CreateColumnUseCase
    delete_column_use_case: DeleteColumnUseCase
    create_card_use_case: CreateCardUseCase
    patch_card_use_case: PatchCardUseCase
    get_card_use_case: GetCardUseCase
    check_readiness_use_case: CheckReadinessUseCase

    def board(self, title: str = "Board") -> AppBoardSummary:
        return _expect_app_ok(
            self.create_board_use_case.execute(CreateBoardCommand(title=title))
        )

    def get_board(self, board_id: str) -> Result[Any, Any]:
        return self.get_board_use_case.execute(GetBoardQuery(board_id=board_id))

    def get_card(self, card_id: str) -> Result[Any, Any]:
        return self.get_card_use_case.execute(GetCardQuery(card_id=card_id))

    @classmethod
    def build_default(cls, database_url: str) -> HandlerHarness:
        repository = SQLModelKanbanRepository(database_url)
        id_gen = FakeIdGenerator()
        clock = FakeClock(datetime(2024, 1, 1, tzinfo=timezone.utc))
        return cls(
            repository=repository,
            create_board_use_case=CreateBoardUseCase(
                uow=SqlModelUnitOfWork(repository.engine),
                id_gen=id_gen,
                clock=clock,
            ),
            patch_board_use_case=PatchBoardUseCase(
                uow=SqlModelUnitOfWork(repository.engine),
            ),
            delete_board_use_case=DeleteBoardUseCase(
                uow=SqlModelUnitOfWork(repository.engine),
            ),
            get_board_use_case=GetBoardUseCase(
                query_repository=KanbanQueryRepositoryView(repository),
            ),
            list_boards_use_case=ListBoardsUseCase(
                query_repository=KanbanQueryRepositoryView(repository),
            ),
            create_column_use_case=CreateColumnUseCase(
                uow=SqlModelUnitOfWork(repository.engine),
                id_gen=id_gen,
            ),
            delete_column_use_case=DeleteColumnUseCase(
                uow=SqlModelUnitOfWork(repository.engine),
            ),
            create_card_use_case=CreateCardUseCase(
                uow=SqlModelUnitOfWork(repository.engine),
                id_gen=id_gen,
            ),
            patch_card_use_case=PatchCardUseCase(
                uow=SqlModelUnitOfWork(repository.engine),
            ),
            get_card_use_case=GetCardUseCase(
                query_repository=KanbanQueryRepositoryView(repository),
            ),
            check_readiness_use_case=CheckReadinessUseCase(readiness=repository),
        )

    def close(self) -> None:
        self.repository.close()

    def column(self, board_id: str, title: str = "Todo") -> AppColumn:
        return _expect_app_ok(
            self.create_column_use_case.execute(
                CreateColumnCommand(board_id=board_id, title=title)
            )
        )

    def delete_column(self, column_id: str) -> Result[Any, Any]:
        return self.delete_column_use_case.execute(
            DeleteColumnCommand(column_id=column_id)
        )

    def card(
        self,
        column_id: str,
        title: str = "Task",
        description: str | None = None,
        *,
        priority: AppCardPriority = AppCardPriority.MEDIUM,
        due_at: datetime | None = None,
    ) -> AppCard:
        return _expect_app_ok(
            self.create_card_use_case.execute(
                CreateCardCommand(
                    column_id=column_id,
                    title=title,
                    description=description,
                    priority=priority,
                    due_at=due_at,
                )
            )
        )

    def patch_card(self, command: PatchCardCommand) -> Result[Any, Any]:
        return self.patch_card_use_case.execute(command)

    def health_ready(self) -> bool:
        return self.check_readiness_use_case.execute(HealthCheckQuery())


def require_str(payload: JsonDict, key: str) -> str:
    value = payload.get(key)
    assert isinstance(value, str)
    return value


def _expect_json_dict(response: Response, *, expected_status: int) -> JsonDict:
    assert response.status_code == expected_status
    payload = response.json()
    assert isinstance(payload, dict)
    return cast(JsonDict, payload)


@dataclass(slots=True)
class ApiBuilder:
    client: TestClient

    def board(self, title: str = "Board") -> JsonDict:
        response = self.client.post("/api/boards", json={"title": title})
        return _expect_json_dict(response, expected_status=201)

    def board_id(self, title: str = "Board") -> str:
        return require_str(self.board(title), "id")

    def column(self, board_id: str, title: str = "Todo") -> JsonDict:
        response = self.client.post(
            f"/api/boards/{board_id}/columns",
            json={"title": title},
        )
        return _expect_json_dict(response, expected_status=201)

    def column_id(self, board_id: str, title: str = "Todo") -> str:
        return require_str(self.column(board_id, title), "id")

    def card(
        self,
        column_id: str,
        title: str = "Task",
        description: str | None = None,
        *,
        priority: PriorityLiteral | None = None,
        due_at: str | None = None,
    ) -> JsonDict:
        payload: JsonDict = {"title": title, "description": description}
        if priority is not None:
            payload["priority"] = priority
        if due_at is not None:
            payload["due_at"] = due_at

        response = self.client.post(f"/api/columns/{column_id}/cards", json=payload)
        return _expect_json_dict(response, expected_status=201)

    def card_id(
        self,
        column_id: str,
        title: str = "Task",
        description: str | None = None,
        *,
        priority: PriorityLiteral | None = None,
        due_at: str | None = None,
    ) -> str:
        return require_str(
            self.card(
                column_id,
                title,
                description,
                priority=priority,
                due_at=due_at,
            ),
            "id",
        )
