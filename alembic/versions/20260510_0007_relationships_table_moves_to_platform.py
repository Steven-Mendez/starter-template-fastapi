"""relationships: ownership moves from auth feature to platform

Revision ID: 20260510_0007
Revises: 20260509_0006
Create Date: 2026-05-10 00:00:00.000000

No-op migration. The ``relationships`` table's Python ownership has
moved from
``src/features/auth/adapters/outbound/persistence/sqlmodel/models.py``
to ``src/platform/persistence/sqlmodel/authorization/models.py`` as
part of the ``split-authentication-and-authorization`` change. The
SQLAlchemy ``MetaData`` is shared, so the DDL Alembic sees is
identical to the previous revision; this revision exists only to
anchor the move in migration history and keep future autogenerates
clean.
"""

from __future__ import annotations

from collections.abc import Sequence

revision: str = "20260510_0007"
down_revision: str | None = "20260509_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """No schema change. See module docstring."""


def downgrade() -> None:
    """No schema change. See module docstring."""
