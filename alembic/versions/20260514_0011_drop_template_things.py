"""template feature: drop things table

Revision ID: 20260514_0011
Revises: 20260513_0010
Create Date: 2026-05-14 00:00:00.000000

The ``_template`` feature has been removed (see the
``remove-template-feature`` OpenSpec change). This revision purges any
``relationships`` rows scoped to the ``thing`` resource type and drops
the ``things`` table itself.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260514_0011"
down_revision: str | None = "20260513_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(sa.text("DELETE FROM relationships WHERE resource_type = 'thing'"))
    op.drop_index("ix_things_owner_id", table_name="things")
    op.drop_table("things")


def downgrade() -> None:
    # Re-creates the table shape from revision 20260511_0008. Rows in
    # ``things`` and the ``thing``-scoped ``relationships`` rows are not
    # restored — recover from backup if a real rollback is needed.
    op.create_table(
        "things",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False
        ),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("char_length(trim(name)) > 0", name="things_name_not_blank"),
    )
    op.create_index("ix_things_owner_id", "things", ["owner_id"])
