"""Query DTOs for the Kanban application layer."""

from src.application.queries.get_board import GetBoardQuery
from src.application.queries.get_card import GetCardQuery
from src.application.queries.health_check import HealthCheckQuery
from src.application.queries.list_boards import ListBoardsQuery

__all__ = [
    "GetBoardQuery",
    "GetCardQuery",
    "HealthCheckQuery",
    "ListBoardsQuery",
]
