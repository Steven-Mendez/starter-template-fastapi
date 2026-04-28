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
    KanbanCommandHandlers,
)
from src.application.contracts import (
    AppBoardSummary,
    AppCard,
    AppCardPriority,
    AppColumn,
)
from src.application.queries import KanbanQueryHandlers
from src.application.shared import AppErr, AppOk, AppResult
from src.domain.kanban.models import (
    Board,
    Card,
    Column,
)
from src.domain.kanban.models import (
    CardPriority as DomainCardPriority,
)
from src.domain.shared.errors import KanbanError
from src.domain.shared.result import Result, expect_ok
from src.infrastructure.persistence.sqlmodel_repository import SQLModelKanbanRepository
from src.infrastructure.persistence.sqlmodel_uow import SqlModelUnitOfWork
from tests.support.fakes import FakeClock, FakeIdGenerator

type JsonDict = dict[str, Any]
type PriorityLiteral = Literal["low", "medium", "high"]


class KanbanBuilderRepository(Protocol):
    def save(self, board: Board) -> None: ...

    def list_all(self) -> list[AppBoardSummary]: ...

    def find_by_id(self, board_id: str) -> Result[Board, KanbanError]: ...

    def remove(self, board_id: str) -> Result[None, KanbanError]: ...

    def find_board_id_by_column(self, column_id: str) -> str | None: ...

    def find_board_id_by_card(self, card_id: str) -> str | None: ...


_T = TypeVar("_T")
_E = TypeVar("_E")


def _expect_app_ok(result: AppResult[_T, _E]) -> _T:
    match result:
        case AppOk(value=v):
            return v
        case AppErr(error=e):
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
        board.columns.append(column)
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
    commands: KanbanCommandHandlers
    queries: KanbanQueryHandlers

    def board(self, title: str = "Board") -> AppBoardSummary:
        return _expect_app_ok(
            self.commands.handle_create_board(CreateBoardCommand(title=title))
        )

    @classmethod
    def build_default(cls, database_url: str) -> HandlerHarness:
        repository = SQLModelKanbanRepository(database_url)
        return cls(
            repository=repository,
            commands=KanbanCommandHandlers(
                uow=SqlModelUnitOfWork(repository.engine),
                id_gen=FakeIdGenerator(),
                clock=FakeClock(datetime(2024, 1, 1, tzinfo=timezone.utc)),
            ),
            queries=KanbanQueryHandlers(repository=repository, readiness=repository),
        )

    def close(self) -> None:
        self.repository.close()

    def column(self, board_id: str, title: str = "Todo") -> AppColumn:
        return _expect_app_ok(
            self.commands.handle_create_column(
                CreateColumnCommand(board_id=board_id, title=title)
            )
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
            self.commands.handle_create_card(
                CreateCardCommand(
                    column_id=column_id,
                    title=title,
                    description=description,
                    priority=priority,
                    due_at=due_at,
                )
            )
        )


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
