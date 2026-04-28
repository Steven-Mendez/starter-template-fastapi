"""add concurrency and position constraints

Revision ID: 20260427_0002
Revises: 20260413_0001
Create Date: 2026-04-27 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260427_0002"
down_revision: str | None = "20260413_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "boards",
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.alter_column("boards", "version", server_default=None)

    op.create_unique_constraint(
        "uq_columns_board_position",
        "columns_",
        ["board_id", "position"],
        deferrable=True,
        initially="DEFERRED",
    )
    op.create_check_constraint(
        "ck_columns_position_non_negative", "columns_", "position >= 0"
    )

    op.create_unique_constraint(
        "uq_cards_column_position",
        "cards",
        ["column_id", "position"],
        deferrable=True,
        initially="DEFERRED",
    )
    op.create_check_constraint(
        "ck_cards_position_non_negative", "cards", "position >= 0"
    )


def downgrade() -> None:
    op.drop_constraint("ck_cards_position_non_negative", "cards", type_="check")
    op.drop_constraint("uq_cards_column_position", "cards", type_="unique")
    op.drop_constraint("ck_columns_position_non_negative", "columns_", type_="check")
    op.drop_constraint("uq_columns_board_position", "columns_", type_="unique")
    op.drop_column("boards", "version")
