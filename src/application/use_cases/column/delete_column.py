from __future__ import annotations

from dataclasses import dataclass

from src.application.commands.column.delete import (
    DeleteColumnCommand,
    handle_delete_column,
)
from src.application.ports.unit_of_work_port import UnitOfWorkPort
from src.application.shared import ApplicationError, AppResult


@dataclass(slots=True)
class DeleteColumnUseCase:
    uow: UnitOfWorkPort

    def execute(
        self, command: DeleteColumnCommand
    ) -> AppResult[None, ApplicationError]:
        return handle_delete_column(uow=self.uow, command=command)
