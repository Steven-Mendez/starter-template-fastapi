"""kanban soft-delete columns + active-rows partial index

Adds nullable ``deleted_at`` (timestamptz) and ``deletion_id`` (UUID)
columns to ``boards``, ``columns_``, and ``cards``. Also creates a
partial index per table on the ``id`` column filtered by
``deleted_at IS NULL`` so the common active-rows query path stays cheap
without dragging tombstones through index scans.

Revision ID: 20260509_0005
Revises: 20260509_0004
Create Date: 2026-05-09 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260509_0005"
down_revision: str | None = "20260509_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = ("boards", "columns_", "cards")


def upgrade() -> None:
    for table in _TABLES:
        op.add_column(
            table,
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.add_column(
            table,
            sa.Column(
                "deletion_id",
                sa.dialects.postgresql.UUID(as_uuid=True),
                nullable=True,
            ),
        )
        op.create_index(
            f"ix_{table}_active",
            table,
            ["id"],
            unique=False,
            postgresql_where=sa.text("deleted_at IS NULL"),
        )


def downgrade() -> None:
    for table in reversed(_TABLES):
        op.drop_index(f"ix_{table}_active", table_name=table)
        op.drop_column(table, "deletion_id")
        op.drop_column(table, "deleted_at")
