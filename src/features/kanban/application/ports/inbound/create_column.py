from __future__ import annotations

from typing import Protocol

from src.features.kanban.application.commands.column.create import CreateColumnCommand
from src.features.kanban.application.contracts import AppColumn
from src.features.kanban.application.errors import ApplicationError
from src.platform.shared.result import Result


class CreateColumnUseCasePort(Protocol):
    def execute(
        self, command: CreateColumnCommand
    ) -> Result[AppColumn, ApplicationError]: ...
