"""Application use case for Kanban create column behavior."""

from __future__ import annotations

from dataclasses import dataclass

from src.features.kanban.application.commands.column.create import (
    CreateColumnCommand,
)
from src.features.kanban.application.contracts import AppColumn
from src.features.kanban.application.contracts.mappers import to_app_column
from src.features.kanban.application.errors import ApplicationError, from_domain_error
from src.features.kanban.application.ports.outbound.unit_of_work import UnitOfWorkPort
from src.features.kanban.domain.models import Column
from src.platform.shared.id_generator_port import IdGeneratorPort
from src.platform.shared.result import Err, Ok, Result


@dataclass(slots=True)
class CreateColumnUseCase:
    """Append a new column to an existing board, taking the next available position."""

    uow: UnitOfWorkPort
    id_gen: IdGeneratorPort

    def execute(
        self, command: CreateColumnCommand
    ) -> Result[AppColumn, ApplicationError]:
        """Build the column, attach it to the board, save, and return its projection."""
        with self.uow:
            board_result = self.uow.commands.find_by_id(command.board_id)
            if isinstance(board_result, Err):
                return Err(from_domain_error(board_result.error))
            board = board_result.value

            column = Column(
                id=self.id_gen.next_id(),
                board_id=command.board_id,
                title=command.title,
                position=board.next_column_position(),
            )
            board.add_column(column)

            self.uow.commands.save(board)
            self.uow.commit()
            return Ok(to_app_column(column))
