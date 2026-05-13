"""outbox: rename dispatched -> delivered, add failed_at, processed_outbox_messages

Revision ID: 20260516_0013
Revises: 20260515_0012
Create Date: 2026-05-16 00:00:00.000000

Locks in the outbox row-state machine ``pending -> delivered | failed``
introduced by ``fix-outbox-dispatch-idempotency``:

- Renames the terminal-success vocabulary: ``status='dispatched'`` ->
  ``status='delivered'`` and ``dispatched_at`` -> ``delivered_at``.
- Adds ``failed_at`` so the failed state has its own commit timestamp
  (matches the production-vocabulary symmetry with ``delivered_at``).
- Creates the handler-side dedup table ``processed_outbox_messages``.
  Outbox-fed job handlers insert ``id`` (the source ``OutboxMessage.id``)
  inside their own transaction; a duplicate-PK collision is the signal
  that this message was already processed, and the handler MUST treat
  that as ``Ok`` (no-op).

The pending-row partial index is re-shaped to ``(available_at, id)`` in
a separate ``CONCURRENTLY`` migration (revision ``20260517_0014``) so
the index swap does not block writes.

``status`` is a free-text ``String(length=16)`` column (not a Postgres
enum), so the rename is a plain ``UPDATE``. Both directions are
reversible.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260516_0013"
down_revision: str | None = "20260515_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Rename the success-state column. ``ALTER TABLE ... RENAME COLUMN``
    #    is a metadata-only operation in PostgreSQL (no row rewrite).
    op.alter_column(
        "outbox_messages",
        "dispatched_at",
        new_column_name="delivered_at",
    )
    # 2. Back-fill existing rows that still hold the old vocabulary.
    op.execute(
        "UPDATE outbox_messages SET status = 'delivered' WHERE status = 'dispatched'"
    )
    # 3. Add ``failed_at`` so the failed terminal state has its own
    #    timestamp column, symmetric with ``delivered_at``.
    op.add_column(
        "outbox_messages",
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
    )
    # 4. Create the handler-side dedup table.
    op.create_table(
        "processed_outbox_messages",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "processed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    op.drop_table("processed_outbox_messages")
    op.drop_column("outbox_messages", "failed_at")
    op.execute(
        "UPDATE outbox_messages SET status = 'dispatched' WHERE status = 'delivered'"
    )
    op.alter_column(
        "outbox_messages",
        "delivered_at",
        new_column_name="dispatched_at",
    )
