from __future__ import annotations

from typing import Protocol

from src.domain.kanban.repository.command import KanbanCommandRepositoryPort
from src.domain.kanban.repository.query import KanbanQueryRepositoryPort


class KanbanRepositoryPort(
    KanbanQueryRepositoryPort,
    KanbanCommandRepositoryPort,
    Protocol,
):
    pass
