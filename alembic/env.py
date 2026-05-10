"""Alembic migration environment configured from application settings."""

from __future__ import annotations

import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

# Importing the auth models module registers its SQLModel metadata with the
# shared MetaData instance so Alembic can detect auth table changes.
# The noqa suppresses the "imported but unused" warning; the side-effect is intentional.
import src.features.auth.adapters.outbound.persistence.sqlmodel.models  # noqa: F401
from alembic import context
from src.features.kanban.adapters.outbound.persistence.sqlmodel.models import (
    get_sqlmodel_metadata,
)
from src.platform.config.settings import AppSettings

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


_DEFAULT_INI_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/kanban"


def _resolve_database_url() -> str:
    """Resolve the migration target DSN.

    Resolution order:
    1. ``APP_POSTGRESQL_DSN`` from the environment — Docker / CI inject it.
    2. A non-default URL already on the Alembic ``Config`` (e.g., a test
       fixture passing a testcontainer URL via ``set_main_option``). The
       hard-coded local-dev URL in ``alembic.ini`` is treated as "no URL
       set" so it does not shadow the env var or the test fixture.
    3. ``AppSettings().postgresql_dsn`` from the application settings.
    """
    env_dsn = os.getenv("APP_POSTGRESQL_DSN")
    if env_dsn:
        return env_dsn
    existing = config.get_main_option("sqlalchemy.url")
    if existing and existing != _DEFAULT_INI_URL:
        return existing
    return AppSettings().postgresql_dsn


config.set_main_option("sqlalchemy.url", _resolve_database_url())
target_metadata = get_sqlmodel_metadata()


def run_migrations_offline() -> None:
    """Emit migration SQL to stdout without connecting to the database.

    Used when generating SQL for review or applying it through an external
    tool (e.g. as part of a managed-DB change-review process).
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Apply migrations through a live database connection.

    ``NullPool`` prevents Alembic from keeping a connection alive after
    migrations finish, which would otherwise block subsequent
    schema-altering DDL on some databases.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
