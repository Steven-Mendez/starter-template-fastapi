"""SQLModel table definitions for the Kanban persistence adapter."""

from src.infrastructure.persistence.sqlmodel.models.board_table import BoardTable
from src.infrastructure.persistence.sqlmodel.models.card_table import CardTable
from src.infrastructure.persistence.sqlmodel.models.column_table import ColumnTable
from src.infrastructure.persistence.sqlmodel.models.metadata import get_sqlmodel_metadata

__all__ = [
    "BoardTable",
    "CardTable",
    "ColumnTable",
    "get_sqlmodel_metadata",
]
