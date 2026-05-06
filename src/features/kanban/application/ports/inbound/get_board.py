"""Inbound use-case protocol for Kanban get board operations."""

from __future__ import annotations

from typing import Protocol

from src.features.kanban.application.contracts import AppBoard
from src.features.kanban.application.errors import ApplicationError
from src.features.kanban.application.queries.get_board import GetBoardQuery
from src.platform.shared.result import Result


class GetBoardUseCasePort(Protocol):
    """Inbound port to read one board with its columns and cards."""

    def execute(self, query: GetBoardQuery) -> Result[AppBoard, ApplicationError]: ...
