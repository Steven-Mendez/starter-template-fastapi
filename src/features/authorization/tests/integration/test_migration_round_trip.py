"""Integration test for the rebac migration's upgrade + downgrade round trip.

Runs the full migration head against a fresh PostgreSQL container, then
downgrades one revision (back to the RBAC schema), then upgrades again.
The schema must converge so a future operator who needs to roll back
and re-apply this migration finds a clean, usable state.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from alembic import command
from features.authentication.adapters.outbound.persistence.sqlmodel.repository import (
    SQLModelAuthRepository,
)

pytestmark = pytest.mark.integration


@pytest.fixture
def alembic_config(_auth_postgres_url: str) -> Iterator[Config]:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", _auth_postgres_url)
    return cfg


def _table_names(engine: Engine) -> set[str]:
    return set(inspect(engine).get_table_names())


def _index_names(engine: Engine, table: str) -> set[str]:
    return {
        idx["name"]
        for idx in inspect(engine).get_indexes(table)
        if idx["name"] is not None
    }


def test_upgrade_to_head_creates_relationships_and_drops_rbac(
    postgres_auth_repository: SQLModelAuthRepository,
    alembic_config: Config,
) -> None:
    """Bring a fresh database all the way to head, then verify the schema."""
    engine = postgres_auth_repository.engine
    # Reset to a clean slate before running migrations from base.
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))

    command.upgrade(alembic_config, "head")

    tables = _table_names(engine)
    assert "relationships" in tables
    for legacy in ("roles", "permissions", "role_permissions", "user_roles"):
        assert legacy not in tables

    indexes = _index_names(engine, "relationships")
    assert "ix_relationships_resource" in indexes
    assert "ix_relationships_subject" in indexes


def test_relationships_table_move_revision_is_a_no_op(
    postgres_auth_repository: SQLModelAuthRepository,
    alembic_config: Config,
) -> None:
    """The revision that moved table ownership SHALL change no DDL.

    The ``split-authentication-and-authorization`` change relocated
    ``RelationshipTable`` from the auth feature to the platform layer.
    Because Alembic operates on a shared ``MetaData`` instance, the SQL
    output of upgrading to the move revision is identical to the
    revision that precedes it; this test pins that invariant against
    revision ``20260510_0007`` directly so it survives later additions
    to the migration chain.
    """
    engine = postgres_auth_repository.engine
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))

    command.upgrade(alembic_config, "20260510_0007")
    after_move_tables = _table_names(engine)
    after_move_indexes = _index_names(engine, "relationships")

    command.downgrade(alembic_config, "-1")

    assert _table_names(engine) == after_move_tables
    assert _index_names(engine, "relationships") == after_move_indexes


# The rebac round-trip is tested against ``20260512_0009`` — the last revision
# whose ``downgrade()`` is honestly reversible. ``20260513_0010`` drops
# ``users.password_hash`` and, per ``docs/operations.md#migration-policy``, its
# ``downgrade()`` raises ``NotImplementedError`` so production data can't be
# silently re-introduced under a default value. Downgrading past ``0010``
# from ``head`` is therefore intentionally impossible, so this round-trip is
# pinned just before that boundary.
_PRE_DESTRUCTIVE_REVISION = "20260512_0009"


def test_downgrade_to_rbac_restores_legacy_tables(
    postgres_auth_repository: SQLModelAuthRepository,
    alembic_config: Config,
) -> None:
    """Downgrading past the rebac revision restores empty RBAC tables.

    Pinned to the absolute revision id so the test stays correct as new
    migrations are appended above it.
    """
    engine = postgres_auth_repository.engine
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))

    command.upgrade(alembic_config, _PRE_DESTRUCTIVE_REVISION)
    command.downgrade(alembic_config, "20260505_0003")

    tables = _table_names(engine)
    assert "relationships" not in tables
    for legacy in ("roles", "permissions", "role_permissions", "user_roles"):
        assert legacy in tables


def test_round_trip_converges_on_the_same_schema(
    postgres_auth_repository: SQLModelAuthRepository,
    alembic_config: Config,
) -> None:
    """upgrade -> downgrade past the rebac revision -> upgrade SHALL leave
    the schema unchanged.
    """
    engine = postgres_auth_repository.engine
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))

    command.upgrade(alembic_config, _PRE_DESTRUCTIVE_REVISION)
    initial_tables = _table_names(engine)
    initial_indexes = _index_names(engine, "relationships")

    command.downgrade(alembic_config, "20260505_0003")
    command.upgrade(alembic_config, _PRE_DESTRUCTIVE_REVISION)

    assert _table_names(engine) == initial_tables
    assert _index_names(engine, "relationships") == initial_indexes
