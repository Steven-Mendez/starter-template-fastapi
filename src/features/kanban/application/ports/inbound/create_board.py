"""Inbound use-case protocol for Kanban create board operations."""

from __future__ import annotations

from typing import Protocol

from src.features.kanban.application.commands.board.create import CreateBoardCommand
from src.features.kanban.application.contracts import AppBoardSummary
from src.features.kanban.application.errors import ApplicationError
from src.platform.shared.result import Result


class CreateBoardUseCasePort(Protocol):
    """Inbound port that the HTTP layer calls to create a new board."""

    def execute(
        self, command: CreateBoardCommand
    ) -> Result[AppBoardSummary, ApplicationError]: ...
