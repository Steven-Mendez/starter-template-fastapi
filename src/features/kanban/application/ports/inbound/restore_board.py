"""Inbound use-case protocol for Kanban restore board operations."""

from __future__ import annotations

from typing import Protocol

from src.features.kanban.application.commands.board.restore import RestoreBoardCommand
from src.features.kanban.application.errors import ApplicationError
from src.platform.shared.result import Result


class RestoreBoardUseCasePort(Protocol):
    """Inbound port to restore a previously soft-deleted board."""

    def execute(
        self, command: RestoreBoardCommand
    ) -> Result[None, ApplicationError]: ...
