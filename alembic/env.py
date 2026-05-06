"""Alembic migration environment configured from application settings."""

from __future__ import annotations

import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from src.features.kanban.adapters.outbound.persistence.sqlmodel.models import (
    get_sqlmodel_metadata,
)
from src.platform.config.settings import AppSettings

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def _resolve_database_url() -> str:
    env_dsn = os.getenv("APP_POSTGRESQL_DSN")
    if env_dsn:
        return env_dsn
    return AppSettings().postgresql_dsn


config.set_main_option("sqlalchemy.url", _resolve_database_url())
target_metadata = get_sqlmodel_metadata()


def run_migrations_offline() -> None:
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
