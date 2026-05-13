"""rebac: drop rbac, add relationships

Revision ID: 20260509_0006
Revises: 20260509_0005
Create Date: 2026-05-09 23:55:00.000000

This is a greenfield migration: the template ships ReBAC instead of
RBAC, and there is no production data to preserve. Upgrade drops the
four RBAC tables (``roles``, ``permissions``, ``role_permissions``,
``user_roles``) and creates a single ``relationships`` table modeled
on Zanzibar tuples. Downgrade recreates empty RBAC tables for
round-trip migration testing — it does not preserve relationships.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260509_0006"
down_revision: str | None = "20260505_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Drop RBAC tables and create the relationships table."""
    # Greenfield migration: the template ships ReBAC, RBAC tables hold no
    # production data. The downgrade re-creates empty RBAC tables for
    # structural round-trip parity — see docs/operations.md#migration-policy.
    op.drop_table("role_permissions")  # allow: destructive
    op.drop_table("user_roles")  # allow: destructive
    op.drop_table("permissions")  # allow: destructive
    op.drop_table("roles")  # allow: destructive

    op.create_table(
        "relationships",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("resource_type", sa.String(length=50), nullable=False),
        sa.Column("resource_id", sa.String(length=64), nullable=False),
        sa.Column("relation", sa.String(length=50), nullable=False),
        sa.Column("subject_type", sa.String(length=50), nullable=False),
        sa.Column("subject_id", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "resource_type",
            "resource_id",
            "relation",
            "subject_type",
            "subject_id",
            name="uq_relationships_tuple",
        ),
    )
    op.create_index(
        "ix_relationships_resource",
        "relationships",
        ["resource_type", "resource_id", "relation"],
        unique=False,
    )
    op.create_index(
        "ix_relationships_subject",
        "relationships",
        ["subject_type", "subject_id", "resource_type", "relation"],
        unique=False,
    )


def downgrade() -> None:
    """Recreate empty RBAC tables and drop relationships.

    Data is not preserved. Round-trip parity is structural only.
    """
    op.drop_index("ix_relationships_subject", table_name="relationships")
    op.drop_index("ix_relationships_resource", table_name="relationships")
    op.drop_table("relationships")

    op.create_table(
        "roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "name ~ '^[a-z][a-z0-9_]*$'", name="ck_roles_name_normalized"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_roles_name"),
    )
    op.create_index("ix_roles_name", "roles", ["name"], unique=False)

    op.create_table(
        "permissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_permissions_name"),
    )
    op.create_index("ix_permissions_name", "permissions", ["name"], unique=False)

    op.create_table(
        "user_roles",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "role_id"),
    )
    op.create_index("ix_user_roles_user_id", "user_roles", ["user_id"], unique=False)
    op.create_index("ix_user_roles_role_id", "user_roles", ["role_id"], unique=False)

    op.create_table(
        "role_permissions",
        sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("permission_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["permission_id"], ["permissions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("role_id", "permission_id"),
    )
    op.create_index(
        "ix_role_permissions_role_id", "role_permissions", ["role_id"], unique=False
    )
    op.create_index(
        "ix_role_permissions_permission_id",
        "role_permissions",
        ["permission_id"],
        unique=False,
    )
