"""Application use case for restoring a soft-deleted Kanban board."""

from __future__ import annotations

from dataclasses import dataclass

from src.features.kanban.application.commands.board.restore import RestoreBoardCommand
from src.features.kanban.application.errors import ApplicationError, from_domain_error
from src.features.kanban.application.ports.outbound.unit_of_work import UnitOfWorkPort
from src.platform.shared.result import Err, Ok, Result


@dataclass(slots=True)
class RestoreBoardUseCase:
    """Reverse a previous board deletion atomically."""

    uow: UnitOfWorkPort

    def execute(
        self,
        command: RestoreBoardCommand,
    ) -> Result[None, ApplicationError]:
        """Restore the board (and its cascade) in a single unit of work."""
        with self.uow:
            result = self.uow.commands.restore(
                command.board_id, actor_id=command.actor_id
            )
            if isinstance(result, Err):
                return Err(from_domain_error(result.error))
            self.uow.commit()
            return Ok(None)
