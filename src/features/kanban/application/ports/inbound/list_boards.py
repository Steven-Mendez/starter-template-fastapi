"""Inbound use-case protocol for Kanban list boards operations."""

from __future__ import annotations

from typing import Protocol

from src.features.kanban.application.contracts import AppBoardSummary
from src.features.kanban.application.errors import ApplicationError
from src.features.kanban.application.queries.list_boards import ListBoardsQuery
from src.platform.shared.result import Result


class ListBoardsUseCasePort(Protocol):
    def execute(
        self, query: ListBoardsQuery
    ) -> Result[list[AppBoardSummary], ApplicationError]: ...
