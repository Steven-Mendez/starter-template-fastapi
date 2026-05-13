"""outbox: reshape ix_outbox_pending to (available_at, id) CONCURRENTLY

Revision ID: 20260517_0014
Revises: 20260516_0013
Create Date: 2026-05-17 00:00:00.000000

The relay's claim query orders by ``available_at`` and uses
``FOR UPDATE SKIP LOCKED``. Without an ``id`` tiebreaker in the
ordering, SKIP LOCKED can spin on rows sharing an ``available_at``
because the scan order is undefined. The fix is to add ``id`` to the
partial index so the planner has a fully-ordered claim path.

This revision is split from the column-rename migration because
``CREATE INDEX CONCURRENTLY`` cannot run inside a transaction block.
Both the drop and the create run inside Alembic's ``autocommit_block``
so the index swap does not block writes on production-sized tables.

``IF [NOT] EXISTS`` clauses make the migration idempotent against a
re-run after a partial failure (PostgreSQL's CONCURRENTLY operations
can leave behind invalid index objects if interrupted).
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260517_0014"
down_revision: str | None = "20260516_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            "DROP INDEX CONCURRENTLY IF EXISTS ix_outbox_pending"
        )  # allow: destructive
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_outbox_pending "
            "ON outbox_messages (available_at, id) "
            "WHERE status = 'pending'"
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_outbox_pending")
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_outbox_pending "
            "ON outbox_messages (available_at) "
            "WHERE status = 'pending'"
        )
