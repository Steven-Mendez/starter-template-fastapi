"""add first-party auth and rbac

Revision ID: 20260505_0003
Revises:
Create Date: 2026-05-05 00:00:00.000000

Note: kanban-related migrations (0001, 0002, 0004, 0005) were removed as
part of the ``starter-template-foundation`` change. This revision now
serves as the chain root until the migration squash in PR 12.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260505_0003"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create every table backing the auth feature.

    The schema enforces several invariants at the database level so the
    application cannot violate them by accident:

    * ``users.authz_version >= 1`` so a buggy reset cannot revive
      stale tokens.
    * ``roles.name`` and ``permissions.name`` follow the canonical
      naming patterns checked by the application.
    * ``auth_internal_tokens.purpose`` is restricted to the two known
      values, preventing rogue token types from accumulating in the
      table without an associated code path.
    """
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=512), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "is_verified", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("authz_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "authz_version >= 1", name="ck_users_authz_version_positive"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=False)

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
        sa.CheckConstraint(
            "name ~ '^[a-z][a-z0-9_]*:[a-z][a-z0-9_:]*$'",
            name="ck_permissions_name_resource_action",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_permissions_name"),
    )
    op.create_index("ix_permissions_name", "permissions", ["name"], unique=False)

    op.create_table(
        "user_roles",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "role_id"),
        sa.UniqueConstraint("user_id", "role_id", name="uq_user_roles_user_role"),
    )
    op.create_index("ix_user_roles_user_id", "user_roles", ["user_id"], unique=False)
    op.create_index("ix_user_roles_role_id", "user_roles", ["role_id"], unique=False)

    op.create_table(
        "role_permissions",
        sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("permission_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["permission_id"], ["permissions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("role_id", "permission_id"),
        sa.UniqueConstraint(
            "role_id", "permission_id", name="uq_role_permissions_role_permission"
        ),
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

    # family_id groups tokens from the same login chain. Revoking by family_id
    # lets the system invalidate all tokens derived from a potentially stolen
    # original without knowing which specific token was compromised.
    op.create_table(
        "refresh_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("family_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replaced_by_token_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_ip", sa.String(length=255), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.ForeignKeyConstraint(
            ["replaced_by_token_id"], ["refresh_tokens.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_refresh_tokens_hash"),
    )
    op.create_index(
        "ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"], unique=False
    )
    op.create_index(
        "ix_refresh_tokens_family_id", "refresh_tokens", ["family_id"], unique=False
    )
    op.create_index(
        "ix_refresh_tokens_expires_at", "refresh_tokens", ["expires_at"], unique=False
    )
    op.create_index(
        "ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"], unique=False
    )

    op.create_table(
        "auth_audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.String(length=150), nullable=False),
        sa.Column("ip_address", sa.String(length=255), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        # SET NULL rather than CASCADE lets audit events survive a user deletion,
        # which is important for forensics and regulatory compliance.
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_auth_audit_events_user_id", "auth_audit_events", ["user_id"], unique=False
    )
    op.create_index(
        "ix_auth_audit_events_event_type",
        "auth_audit_events",
        ["event_type"],
        unique=False,
    )
    op.create_index(
        "ix_auth_audit_events_created_at",
        "auth_audit_events",
        ["created_at"],
        unique=False,
    )

    op.create_table(
        "auth_internal_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("purpose", sa.String(length=50), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_ip", sa.String(length=255), nullable=True),
        # The CHECK constraint on purpose prevents new token types from being
        # persisted without a corresponding migration, avoiding orphaned rows
        # that no code path will ever consume or expire.
        sa.CheckConstraint(
            "purpose in ('password_reset', 'email_verify')",
            name="ck_auth_internal_tokens_purpose",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_auth_internal_tokens_hash"),
    )
    op.create_index(
        "ix_auth_internal_tokens_user_id",
        "auth_internal_tokens",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_auth_internal_tokens_purpose",
        "auth_internal_tokens",
        ["purpose"],
        unique=False,
    )
    op.create_index(
        "ix_auth_internal_tokens_expires_at",
        "auth_internal_tokens",
        ["expires_at"],
        unique=False,
    )
    op.create_index(
        "ix_auth_internal_tokens_token_hash",
        "auth_internal_tokens",
        ["token_hash"],
        unique=False,
    )


def downgrade() -> None:
    """Drop auth tables in dependency order so teardown avoids foreign-key blocks."""
    op.drop_index(
        "ix_auth_internal_tokens_token_hash", table_name="auth_internal_tokens"
    )
    op.drop_index(
        "ix_auth_internal_tokens_expires_at", table_name="auth_internal_tokens"
    )
    op.drop_index("ix_auth_internal_tokens_purpose", table_name="auth_internal_tokens")
    op.drop_index("ix_auth_internal_tokens_user_id", table_name="auth_internal_tokens")
    op.drop_table("auth_internal_tokens")

    op.drop_index("ix_auth_audit_events_created_at", table_name="auth_audit_events")
    op.drop_index("ix_auth_audit_events_event_type", table_name="auth_audit_events")
    op.drop_index("ix_auth_audit_events_user_id", table_name="auth_audit_events")
    op.drop_table("auth_audit_events")

    op.drop_index("ix_refresh_tokens_token_hash", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_expires_at", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_family_id", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_user_id", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")

    op.drop_index("ix_role_permissions_permission_id", table_name="role_permissions")
    op.drop_index("ix_role_permissions_role_id", table_name="role_permissions")
    op.drop_table("role_permissions")

    op.drop_index("ix_user_roles_role_id", table_name="user_roles")
    op.drop_index("ix_user_roles_user_id", table_name="user_roles")
    op.drop_table("user_roles")

    op.drop_index("ix_permissions_name", table_name="permissions")
    op.drop_table("permissions")

    op.drop_index("ix_roles_name", table_name="roles")
    op.drop_table("roles")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
