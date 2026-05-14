"""users: add is_erased flag for GDPR Art. 17 scrub

Revision ID: 20260519_0016
Revises: 20260518_0015
Create Date: 2026-05-19 00:00:00.000000

GDPR Art. 17 (right to erasure) requires the service to scrub PII for a
user on request without breaking referential integrity of audit-log
rows that point back at the ``users.id``. The ``is_erased`` flag is the
authoritative signal: ``UserPort.get_by_id`` / ``get_by_email`` filter
``is_erased=true`` rows out so cached principals dissolve within their
TTL, and the row itself stays so FKs from ``auth_audit_events`` etc.
remain valid.

The migration is reversible — ``downgrade`` drops the column. There is
no production-data semantics tied to ``is_erased`` on rows that
predate this migration (every existing user is, by definition, not
erased), so the new column simply defaults to ``false``. We use
``server_default`` so backfill happens at column-add time without a
follow-up ``UPDATE`` pass; that keeps the migration single-statement on
small tables and the lock is brief on Postgres 11+ which sets the
default lazily.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260519_0016"
down_revision: str | None = "20260518_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "is_erased",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "is_erased")
