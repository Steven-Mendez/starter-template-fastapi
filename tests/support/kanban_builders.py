from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, Protocol, cast

from fastapi.testclient import TestClient
from httpx import Response

from src.application.commands import (
    CreateBoardCommand,
    CreateCardCommand,
    CreateColumnCommand,
    KanbanCommandHandlers,
)
from src.application.queries import KanbanQueryHandlers
from src.domain.kanban.models import BoardSummary, Card, CardPriority, Column
from src.domain.shared.errors import KanbanError
from src.domain.shared.result import Result, expect_ok

type JsonDict = dict[str, Any]
type PriorityLiteral = Literal["low", "medium", "high"]


class KanbanBuilderRepository(Protocol):
    def create_board(self, title: str) -> BoardSummary: ...

    def create_column(
        self, board_id: str, title: str
    ) -> Result[Column, KanbanError]: ...

    def create_card(
        self,
        column_id: str,
        title: str,
        description: str | None,
        *,
        priority: CardPriority = CardPriority.MEDIUM,
        due_at: datetime | None = None,
    ) -> Result[Card, KanbanError]: ...


@dataclass(slots=True)
class StoreBuilder:
    repository: KanbanBuilderRepository

    def board(self, title: str = "Board") -> BoardSummary:
        return self.repository.create_board(title)

    def column(self, board_id: str, title: str = "Todo") -> Column:
        return expect_ok(self.repository.create_column(board_id, title))

    def card(
        self,
        column_id: str,
        title: str = "Task",
        description: str | None = None,
        *,
        priority: CardPriority = CardPriority.MEDIUM,
        due_at: datetime | None = None,
    ) -> Card:
        return expect_ok(
            self.repository.create_card(
                column_id,
                title,
                description,
                priority=priority,
                due_at=due_at,
            )
        )


@dataclass(slots=True)
class HandlerHarness:
    commands: KanbanCommandHandlers
    queries: KanbanQueryHandlers

    def board(self, title: str = "Board") -> BoardSummary:
        return self.commands.handle_create_board(CreateBoardCommand(title=title))

    def column(self, board_id: str, title: str = "Todo") -> Column:
        return expect_ok(
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
        priority: CardPriority = CardPriority.MEDIUM,
        due_at: datetime | None = None,
    ) -> Card:
        return expect_ok(
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
