from __future__ import annotations

from sqlalchemy.engine import Engine
from sqlmodel import create_engine

from src.platform.config.settings import AppSettings


def build_engine(settings: AppSettings) -> Engine:
    if not settings.postgresql_dsn.startswith("postgresql"):
        msg = "platform.persistence.sqlmodel supports PostgreSQL DSNs only"
        raise ValueError(msg)
    return create_engine(settings.postgresql_dsn, pool_pre_ping=True)
