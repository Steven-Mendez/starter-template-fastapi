"""Inbound use-case protocol for Kanban delete column operations."""

from __future__ import annotations

from typing import Protocol

from src.features.kanban.application.commands.column.delete import DeleteColumnCommand
from src.features.kanban.application.errors import ApplicationError
from src.platform.shared.result import Result


class DeleteColumnUseCasePort(Protocol):
    """Inbound port for deleting a column and re-compacting its sibling positions."""

    def execute(
        self, command: DeleteColumnCommand
    ) -> Result[None, ApplicationError]: ...
