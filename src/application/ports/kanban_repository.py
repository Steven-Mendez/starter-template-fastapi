from __future__ import annotations

from typing import Protocol

from src.application.ports.kanban_command_repository import KanbanCommandRepositoryPort
from src.application.ports.kanban_lookup_repository import KanbanLookupRepositoryPort
from src.application.ports.kanban_query_repository import KanbanQueryRepositoryPort


class KanbanRepositoryPort(
    KanbanQueryRepositoryPort,
    KanbanCommandRepositoryPort,
    KanbanLookupRepositoryPort,
    Protocol,
):
    pass
