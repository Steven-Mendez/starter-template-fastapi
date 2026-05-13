"""authentication: drop users.password_hash (phase 2)

Revision ID: 20260513_0010
Revises: 20260512_0009
Create Date: 2026-05-13 00:00:00.000000

Phase 2 of the credentials split (see the ``starter-template-foundation``
change). Phase 1 (``20260512_0009``) created the ``credentials`` table
and backfilled every existing hash; phase 2 drops the now-redundant
``users.password_hash`` column. Deploy this only after the phase-1
revision has been live in production for at least one release cycle so
the login fallback path has had time to write a credential row for
every active user.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260513_0010"
down_revision: str | None = "20260512_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("users", "password_hash")


def downgrade() -> None:
    raise NotImplementedError(
        "One-way migration: drop of users.password_hash is not safely "
        "reversible. If you need to revert, restore from backup. "
        "See docs/operations.md#migration-policy."
    )
