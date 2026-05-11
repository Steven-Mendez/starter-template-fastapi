"""Outbound port protocol for Kanban unit of work persistence behavior."""

from __future__ import annotations

from types import TracebackType
from typing import Protocol, Self

from src.features.authorization.application.ports.authorization_port import (
    AuthorizationPort,
)
from src.features.kanban.application.ports.outbound.kanban_command_repository import (
    KanbanCommandRepositoryPort,
)
from src.features.kanban.application.ports.outbound.kanban_lookup_repository import (
    KanbanLookupRepositoryPort,
)


class UnitOfWorkPort(Protocol):
    """Outbound port that groups command + lookup + authorization writes.

    Use cases call ``with unit_of_work() as uow:`` to ensure that
    repository writes and the relationship tuples written by the
    authorization layer either commit together or roll back together,
    keeping the :class:`Board` aggregate and its access tuples
    consistent across multi-step operations.
    """

    commands: KanbanCommandRepositoryPort
    lookup: KanbanLookupRepositoryPort
    authorization: AuthorizationPort

    def __enter__(self) -> Self:
        """Begin a transaction and return the unit of work."""
        ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Commit on clean exit and roll back if an exception is propagating."""
        ...

    def commit(self) -> None:
        """Flush pending writes and commit the underlying transaction."""
        ...

    def rollback(self) -> None:
        """Discard any pending writes and roll back the underlying transaction."""
        ...
