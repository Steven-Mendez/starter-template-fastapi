"""template feature: create things table

Revision ID: 20260511_0008
Revises: 20260510_0007
Create Date: 2026-05-11 00:00:00.000000

Adds the ``things`` table owned by the live ``_template`` feature. The
table is intentionally minimal (id, name, owner_id, created_at,
updated_at) so consumers who copy the template can extend it without
having to fight legacy columns.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260511_0008"
down_revision: str | None = "20260510_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "things",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False
        ),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column(
            "owner_id", postgresql.UUID(as_uuid=True), nullable=False, index=True
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("char_length(trim(name)) > 0", name="things_name_not_blank"),
    )
    op.create_index("ix_things_owner_id", "things", ["owner_id"])


def downgrade() -> None:
    op.drop_index("ix_things_owner_id", table_name="things")
    op.drop_table("things")
