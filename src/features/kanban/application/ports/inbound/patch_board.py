"""Inbound use-case protocol for Kanban patch board operations."""

from __future__ import annotations

from typing import Protocol

from src.features.kanban.application.commands.board.patch import PatchBoardCommand
from src.features.kanban.application.contracts import AppBoardSummary
from src.features.kanban.application.errors import ApplicationError
from src.platform.shared.result import Result


class PatchBoardUseCasePort(Protocol):
    """Inbound port for sparse updates to an existing board."""

    def execute(
        self, command: PatchBoardCommand
    ) -> Result[AppBoardSummary, ApplicationError]: ...
