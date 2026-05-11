"""Application use case for Kanban create board behavior."""

from __future__ import annotations

from dataclasses import dataclass

from src.features.authorization.application.types import Relationship
from src.features.kanban.application.commands.board.create import CreateBoardCommand
from src.features.kanban.application.contracts import AppBoardSummary
from src.features.kanban.application.errors import ApplicationError
from src.features.kanban.application.persistence_errors import PersistenceConflictError
from src.features.kanban.application.ports.outbound.unit_of_work import UnitOfWorkPort
from src.features.kanban.domain.models import Board
from src.platform.shared.clock_port import ClockPort
from src.platform.shared.id_generator_port import IdGeneratorPort
from src.platform.shared.result import Err, Ok, Result


@dataclass(slots=True)
class CreateBoardUseCase:
    """Create a new empty board, persist it, and grant its creator ownership.

    The board insert and the initial ``kanban:{board.id}#owner@user:{actor}``
    tuple share one transaction so a partial failure cannot leave a board
    with no owner — and therefore no path to delete or restore it.
    """

    uow: UnitOfWorkPort
    id_gen: IdGeneratorPort
    clock: ClockPort

    def execute(
        self,
        command: CreateBoardCommand,
    ) -> Result[AppBoardSummary, ApplicationError]:
        """Save the new board + owner relationship and return its summary."""
        board = Board(
            id=self.id_gen.next_id(),
            title=command.title,
            created_at=self.clock.now(),
            created_by=command.actor_id,
            updated_by=command.actor_id,
        )
        with self.uow:
            try:
                self.uow.commands.save(board)
                if command.actor_id is not None:
                    self.uow.authorization.write_relationships(
                        [
                            Relationship(
                                resource_type="kanban",
                                resource_id=board.id,
                                relation="owner",
                                subject_type="user",
                                subject_id=str(command.actor_id),
                            )
                        ]
                    )
                self.uow.commit()
            except PersistenceConflictError:
                return Err(ApplicationError.STALE_WRITE)
            return Ok(
                AppBoardSummary(
                    id=board.id,
                    title=board.title,
                    created_at=board.created_at,
                )
            )
