from __future__ import annotations

from typing import Protocol

from src.features.kanban.application.commands.board.delete import DeleteBoardCommand
from src.features.kanban.application.errors import ApplicationError
from src.platform.shared.result import Result


class DeleteBoardUseCasePort(Protocol):
    def execute(
        self, command: DeleteBoardCommand
    ) -> Result[None, ApplicationError]: ...
