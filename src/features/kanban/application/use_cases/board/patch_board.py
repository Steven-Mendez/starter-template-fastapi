"""Application use case for Kanban patch board behavior."""

from __future__ import annotations

from dataclasses import dataclass

from src.features.kanban.application.commands.board.patch import PatchBoardCommand
from src.features.kanban.application.contracts import AppBoardSummary
from src.features.kanban.application.errors import ApplicationError, from_domain_error
from src.features.kanban.application.ports.outbound.unit_of_work import UnitOfWorkPort
from src.platform.shared.result import Err, Ok, Result


@dataclass(slots=True)
class PatchBoardUseCase:
    """Apply a sparse update to an existing board (currently just ``title``).

    Empty patches are rejected explicitly so an idle ``PATCH`` request
    never produces an unnecessary write or an audit-log entry.
    """

    uow: UnitOfWorkPort

    def execute(
        self,
        command: PatchBoardCommand,
    ) -> Result[AppBoardSummary, ApplicationError]:
        """Patch the board in a UoW and return its summary projection."""
        if not command.has_changes():
            return Err(ApplicationError.PATCH_NO_CHANGES)

        with self.uow:
            result = self.uow.commands.find_by_id(command.board_id)
            if isinstance(result, Err):
                return Err(from_domain_error(result.error))
            board = result.value
            if command.title is not None:
                board.rename(command.title)
            self.uow.commands.save(board)
            self.uow.commit()
            return Ok(
                AppBoardSummary(
                    id=board.id,
                    title=board.title,
                    created_at=board.created_at,
                )
            )
