from __future__ import annotations

from typing import Protocol

from src.domain.kanban.repository.command import KanbanCommandRepository
from src.domain.kanban.repository.query import KanbanQueryRepository


class KanbanRepository(KanbanQueryRepository, KanbanCommandRepository, Protocol):
    pass
