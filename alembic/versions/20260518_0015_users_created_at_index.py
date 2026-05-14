"""users: add ix_users_created_at CONCURRENTLY for keyset pagination

Revision ID: 20260518_0015
Revises: 20260517_0014
Create Date: 2026-05-18 00:00:00.000000

The admin ``GET /admin/users`` endpoint paginates by a
``(created_at, id)`` keyset cursor:

    WHERE (created_at, id) > (:c, :i)
    ORDER BY created_at, id
    LIMIT :limit

Without a composite index on ``(created_at, id)`` the query falls back
to a full sort and the deep-page latency grows linearly with the table.
Adding the index turns every page into a constant-time index range scan.

The build uses ``CREATE INDEX CONCURRENTLY`` (via
``alembic.migration_helpers.create_index_concurrently``) so the
migration does not block writes on a populated production ``users``
table. CONCURRENTLY cannot run inside a transaction; the helper wraps
the statement in Alembic's ``autocommit_block`` for us.
"""

from __future__ import annotations

from collections.abc import Sequence

from migration_helpers import (
    create_index_concurrently,
    drop_index_concurrently,
)

revision: str = "20260518_0015"
down_revision: str | None = "20260517_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    create_index_concurrently(
        "ix_users_created_at",
        "users",
        ["created_at", "id"],
    )


def downgrade() -> None:
    drop_index_concurrently("ix_users_created_at")
