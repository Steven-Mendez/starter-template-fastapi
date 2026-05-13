"""outbox: create outbox_messages table

Revision ID: 20260515_0012
Revises: 20260514_0011
Create Date: 2026-05-15 00:00:00.000000

Adds the transactional-outbox table. Producer transactions insert one
row per side-effect intent; the worker's relay tick claims pending
rows under ``FOR UPDATE SKIP LOCKED`` and dispatches them through
``JobQueuePort``.

The partial index on ``status='pending'`` is the relay's primary access
path — keeping the index tight on just-pending rows keeps the claim
scan cheap once dispatched rows accumulate. Alembic's autogenerate
omits filtered indexes, so the index is created explicitly here.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260515_0012"
down_revision: str | None = "20260514_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "outbox_messages",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("job_name", sa.String(length=128), nullable=False),
        sa.Column("payload", postgresql.JSONB, nullable=False),
        sa.Column(
            "available_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "attempts",
            sa.Integer,
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_by", sa.String(length=128), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_outbox_pending",
        "outbox_messages",
        ["available_at"],
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.create_index("ix_outbox_created", "outbox_messages", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_outbox_created", table_name="outbox_messages")
    op.drop_index("ix_outbox_pending", table_name="outbox_messages")
    op.drop_table("outbox_messages")
