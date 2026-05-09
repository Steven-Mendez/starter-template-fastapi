"""kanban audit columns (created_by / updated_by)

Adds nullable UUID audit columns to ``boards``, ``columns_``, and
``cards``. The columns intentionally have no foreign key to
``auth.users``: kanban must remain schema-isolated from the auth
feature so either can move independently. Referential integrity is
enforced at the application layer instead.

Revision ID: 20260509_0004
Revises: 20260505_0003
Create Date: 2026-05-09 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260509_0004"
down_revision: str | None = "20260505_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = ("boards", "columns_", "cards")


def upgrade() -> None:
    for table in _TABLES:
        op.add_column(
            table,
            sa.Column(
                "created_by", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True
            ),
        )
        op.add_column(
            table,
            sa.Column(
                "updated_by", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True
            ),
        )


def downgrade() -> None:
    for table in reversed(_TABLES):
        op.drop_column(table, "updated_by")
        op.drop_column(table, "created_by")
