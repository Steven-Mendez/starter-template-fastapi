"""authentication: extract credentials into a dedicated table (phase 1)

Revision ID: 20260512_0009
Revises: 20260511_0008
Create Date: 2026-05-12 00:00:00.000000

Phase 1 of the credentials split (see the ``starter-template-foundation``
change). Creates the ``credentials`` table and copies every existing
``users.password_hash`` row into it under ``algorithm='argon2'``. The
``users.password_hash`` column is kept in place so the login fallback
path can still read it during the rollout; the column is dropped in
phase 2 (``20260513_0010``).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260512_0009"
down_revision: str | None = "20260511_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "credentials",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("algorithm", sa.String(length=32), nullable=False),
        sa.Column("hash", sa.String(length=512), nullable=False),
        sa.Column("last_changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "user_id", "algorithm", name="uq_credentials_user_id_algorithm"
        ),
    )
    op.create_index("ix_credentials_user_id", "credentials", ["user_id"])

    # Backfill: copy every existing password hash into the new table so
    # users can log in immediately after the migration. Only rows with a
    # non-empty hash are copied — empty strings are sentinels written by
    # post-migration code paths that route credentials through this table
    # directly and have nothing to backfill.
    op.execute(
        sa.text(
            """
            INSERT INTO credentials (
                id, user_id, algorithm, hash, last_changed_at, created_at
            )
            SELECT
                gen_random_uuid(),
                id,
                'argon2',
                password_hash,
                COALESCE(updated_at, NOW()),
                COALESCE(created_at, NOW())
            FROM users
            WHERE password_hash IS NOT NULL AND password_hash <> ''
            """
        )
    )


def downgrade() -> None:
    op.drop_index("ix_credentials_user_id", table_name="credentials")
    op.drop_table("credentials")
