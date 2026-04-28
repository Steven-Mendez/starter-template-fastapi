"""SQLModel table definitions for the Kanban persistence adapter."""

from .board_table import BoardTable
from .card_table import CardTable
from .column_table import ColumnTable
from .metadata import get_sqlmodel_metadata

__all__ = [
    "BoardTable",
    "CardTable",
    "ColumnTable",
    "get_sqlmodel_metadata",
]
