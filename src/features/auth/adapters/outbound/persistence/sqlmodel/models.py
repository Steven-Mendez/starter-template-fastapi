"""SQLModel table definitions for the auth feature.

These mappings own the database schema for users, roles, permissions,
their join tables, refresh tokens, internal (single-use) tokens, and the
auth audit log. Every timestamp is timezone-aware UTC and ID columns are
UUIDs so the schema is portable across PostgreSQL replicas without
relying on a sequence.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    """Return the current UTC time as a timezone-aware datetime.

    Centralising this helper guarantees every persisted timestamp uses the
    same convention, avoiding mismatches between naive and aware values
    that would surface as confusing comparison failures later.
    """
    return datetime.now(timezone.utc)


class UserTable(SQLModel, table=True):
    """User account row.

    Holds the password hash, activity flags, and the ``authz_version``
    counter used to invalidate already-issued JWTs whenever a user's
    permissions or status change.
    """

    __tablename__ = "users"
    __table_args__ = (
        sa.UniqueConstraint("email", name="uq_users_email"),
        # authz_version only ever increases, so a DB-level CHECK constraint
        # prevents accidental resets to 0 that would silently re-validate
        # tokens which the application had already invalidated.
        sa.CheckConstraint(
            "authz_version >= 1", name="ck_users_authz_version_positive"
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    email: str = Field(index=True, nullable=False)
    password_hash: str = Field(nullable=False)
    is_active: bool = Field(default=True, nullable=False)
    is_verified: bool = Field(default=False, nullable=False)
    authz_version: int = Field(default=1, nullable=False)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False),
    )
    last_login_at: datetime | None = Field(
        default=None,
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=True),
    )


class RoleTable(SQLModel, table=True):
    """Role definition.

    ``is_active=False`` disables the role globally without deleting assignments.
    """

    __tablename__ = "roles"
    __table_args__ = (sa.UniqueConstraint("name", name="uq_roles_name"),)

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(index=True, nullable=False)
    description: str | None = Field(default=None)
    is_active: bool = Field(default=True, nullable=False)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False),
    )


class PermissionTable(SQLModel, table=True):
    """Permission definition, named with the ``resource:action`` convention."""

    __tablename__ = "permissions"
    __table_args__ = (sa.UniqueConstraint("name", name="uq_permissions_name"),)

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(index=True, nullable=False)
    description: str | None = Field(default=None)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False),
    )


class UserRoleTable(SQLModel, table=True):
    """Join table linking users to roles.

    Composite PK prevents duplicate assignments.
    """

    __tablename__ = "user_roles"

    user_id: UUID = Field(foreign_key="users.id", primary_key=True)
    role_id: UUID = Field(foreign_key="roles.id", primary_key=True)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False),
    )


class RolePermissionTable(SQLModel, table=True):
    """Join table linking roles to their granted permissions."""

    __tablename__ = "role_permissions"

    role_id: UUID = Field(foreign_key="roles.id", primary_key=True)
    permission_id: UUID = Field(foreign_key="permissions.id", primary_key=True)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False),
    )


class RefreshTokenTable(SQLModel, table=True):
    """Refresh token row.

    Stores only the SHA-256 hash of the token so a database dump never
    exposes bearer credentials. ``family_id`` groups every token issued
    from a single login chain so reuse detection can revoke the whole
    family at once. ``replaced_by_token_id`` keeps an audit chain back to
    the original login without persisting the raw token values.
    """

    __tablename__ = "refresh_tokens"
    __table_args__ = (sa.UniqueConstraint("token_hash", name="uq_refresh_tokens_hash"),)

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", index=True, nullable=False)
    token_hash: str = Field(index=True, nullable=False)
    family_id: UUID = Field(index=True, nullable=False)
    expires_at: datetime = Field(
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False, index=True)
    )
    revoked_at: datetime | None = Field(
        default=None,
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=True),
    )
    replaced_by_token_id: UUID | None = Field(
        default=None, foreign_key="refresh_tokens.id"
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False),
    )
    created_ip: str | None = Field(default=None)
    user_agent: str | None = Field(default=None)


class AuthAuditEventTable(SQLModel, table=True):
    """Append-only audit log row for any auth/RBAC-relevant action."""

    __tablename__ = "auth_audit_events"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID | None = Field(default=None, foreign_key="users.id", index=True)
    event_type: str = Field(index=True, nullable=False)
    ip_address: str | None = Field(default=None)
    user_agent: str | None = Field(default=None)
    event_metadata: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=sa.Column("metadata", sa.JSON(), nullable=False),
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False, index=True),
    )


class AuthInternalTokenTable(SQLModel, table=True):
    """Single-use, short-lived token used for password resets and email verification.

    Living in a dedicated table keeps the flow decoupled from the actual
    email delivery infrastructure and makes expiry and usage auditing
    trivial: the ``used_at`` timestamp is the consumption marker.
    """

    __tablename__ = "auth_internal_tokens"
    __table_args__ = (
        sa.UniqueConstraint("token_hash", name="uq_auth_internal_tokens_hash"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID | None = Field(default=None, foreign_key="users.id", index=True)
    purpose: str = Field(index=True, nullable=False)
    token_hash: str = Field(index=True, nullable=False)
    expires_at: datetime = Field(
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False, index=True)
    )
    used_at: datetime | None = Field(
        default=None,
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=True),
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False),
    )
    created_ip: str | None = Field(default=None)


__all__ = [
    "AuthAuditEventTable",
    "AuthInternalTokenTable",
    "PermissionTable",
    "RefreshTokenTable",
    "RolePermissionTable",
    "RoleTable",
    "UserRoleTable",
    "UserTable",
    "utc_now",
]
