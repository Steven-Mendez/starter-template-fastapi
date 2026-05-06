"""SQLModel metadata accessor used by Alembic."""

from __future__ import annotations

import sqlalchemy as sa
from sqlmodel import SQLModel


def get_sqlmodel_metadata() -> sa.MetaData:
    """Return the shared SQLModel metadata object that Alembic should target.

    Centralising the accessor here lets the Alembic env file stay
    decoupled from any specific feature's import path.
    """
    return SQLModel.metadata
