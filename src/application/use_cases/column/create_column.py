from __future__ import annotations

from dataclasses import dataclass

from src.application.commands.column.create import (
    CreateColumnCommand,
)
from src.application.contracts import AppColumn
from src.application.contracts.mappers import to_app_column
from src.application.kanban.errors import ApplicationError, from_domain_error
from src.application.ports.id_generator_port import IdGeneratorPort
from src.application.ports.unit_of_work_port import UnitOfWorkPort
from src.domain.kanban.models import Column
from src.domain.shared.result import Err, Ok, Result


@dataclass(slots=True)
class CreateColumnUseCase:
    uow: UnitOfWorkPort
    id_gen: IdGeneratorPort

    def execute(
        self, command: CreateColumnCommand
    ) -> Result[AppColumn, ApplicationError]:
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
