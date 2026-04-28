from __future__ import annotations

from dataclasses import dataclass

from src.application.commands.column.create import (
    CreateColumnCommand,
    handle_create_column,
)
from src.application.contracts import AppColumn
from src.application.ports.id_generator_port import IdGeneratorPort
from src.application.ports.unit_of_work_port import UnitOfWorkPort
from src.application.shared import ApplicationError, AppResult


@dataclass(slots=True)
class CreateColumnUseCase:
    uow: UnitOfWorkPort
    id_gen: IdGeneratorPort

    def execute(
        self, command: CreateColumnCommand
    ) -> AppResult[AppColumn, ApplicationError]:
        return handle_create_column(uow=self.uow, id_gen=self.id_gen, command=command)
