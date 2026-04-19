from __future__ import annotations

import sqlalchemy as sa
from sqlmodel import SQLModel


def get_sqlmodel_metadata() -> sa.MetaData:
    return SQLModel.metadata
