"""SQLModel engine factory for PostgreSQL persistence."""

from __future__ import annotations

from sqlalchemy.engine import Engine
from sqlmodel import create_engine

from src.platform.config.settings import AppSettings


def build_engine(settings: AppSettings) -> Engine:
    """Create a SQLAlchemy engine configured for the application's PostgreSQL DSN.

    ``pool_pre_ping`` is enabled so connections that the database has
    closed (after a restart or idle timeout) are silently recycled rather
    than surfacing as errors on the first query.

    Args:
        settings: Application settings; ``postgresql_dsn`` must be PostgreSQL.

    Returns:
        A ready-to-use SQLAlchemy ``Engine``.

    Raises:
        ValueError: If ``settings.postgresql_dsn`` does not start with ``"postgresql"``.
    """
    if not settings.postgresql_dsn.startswith("postgresql"):
        msg = "platform.persistence.sqlmodel supports PostgreSQL DSNs only"
        raise ValueError(msg)
    return create_engine(settings.postgresql_dsn, pool_pre_ping=True)
