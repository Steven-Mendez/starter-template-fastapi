"""Helpers for non-blocking index changes in Alembic migrations.

PostgreSQL's ``CREATE INDEX`` (and ``DROP INDEX``) take an
``ACCESS EXCLUSIVE`` lock on the target table, which is fine on a
developer laptop but catastrophic on a populated production table — the
DDL queues behind every reader and blocks every writer for the duration
of the build.

``CREATE INDEX CONCURRENTLY`` avoids the heavy lock at the cost of a
longer wall-clock time and a constraint that the statement cannot run
inside a transaction. Alembic exposes this through
``op.get_context().autocommit_block()``, which temporarily switches the
underlying connection to autocommit mode for the duration of the with
block.

Usage::

    from migration_helpers import (
        create_index_concurrently,
        drop_index_concurrently,
    )

(``alembic/`` is on ``sys.path`` via ``prepend_sys_path`` in
``alembic.ini``; the helper is imported as a top-level module to avoid
colliding with the installed ``alembic`` PyPI package.)

    def upgrade() -> None:
        create_index_concurrently(
            "ix_users_created_at",
            "users",
            ["created_at", "id"],
        )

    def downgrade() -> None:
        drop_index_concurrently("ix_users_created_at")

The helpers emit ``IF [NOT] EXISTS`` so a re-run after a partial failure
is idempotent. PostgreSQL's CONCURRENTLY operations can leave behind an
invalid index object if interrupted; the ``IF NOT EXISTS`` makes the
follow-up migration safe to re-apply.

Convention: any migration touching a table expected to hold production
data MUST use these helpers for index changes. See ``docs/architecture.md``
for the rule and ``CLAUDE.md`` for the contributor reminder.
"""

from __future__ import annotations

from collections.abc import Iterable

from alembic import op


def _format_columns(columns: Iterable[str]) -> str:
    cols = list(columns)
    if not cols:
        raise ValueError("create_index_concurrently requires at least one column")
    return ", ".join(cols)


def create_index_concurrently(
    name: str,
    table: str,
    columns: Iterable[str],
    *,
    where: str | None = None,
    unique: bool = False,
) -> None:
    """Issue ``CREATE INDEX CONCURRENTLY`` inside an autocommit block.

    Args:
        name: Index name. Must be unique within the schema.
        table: Target table name.
        columns: One or more column names that make up the index.
        where: Optional partial-index predicate (without the ``WHERE``).
        unique: When True, emit ``UNIQUE INDEX``. Note that creating a
            unique index concurrently can fail if duplicate rows exist;
            consider an offline path for the initial backfill.

    The statement is wrapped in ``op.get_context().autocommit_block()``
    because ``CREATE INDEX CONCURRENTLY`` cannot run inside a transaction.
    The ``IF NOT EXISTS`` clause makes the operation idempotent against
    a re-run after a partial failure.
    """
    cols_sql = _format_columns(columns)
    uniqueness = "UNIQUE " if unique else ""
    where_sql = f" WHERE {where}" if where else ""
    sql = (
        f"CREATE {uniqueness}INDEX CONCURRENTLY IF NOT EXISTS {name} "
        f"ON {table} ({cols_sql}){where_sql}"
    )
    with op.get_context().autocommit_block():
        op.execute(sql)


def drop_index_concurrently(name: str) -> None:
    """Issue ``DROP INDEX CONCURRENTLY`` inside an autocommit block.

    Args:
        name: Index name to drop.

    Like the create helper, the statement runs in autocommit mode and
    uses ``IF EXISTS`` so the migration is safe to re-apply.
    """
    with op.get_context().autocommit_block():
        op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {name}")


__all__ = ["create_index_concurrently", "drop_index_concurrently"]
