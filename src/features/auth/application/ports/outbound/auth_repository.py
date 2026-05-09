"""Outbound port protocol for auth persistence.

The application layer depends on this protocol, never on the concrete
SQLModel adapter, keeping the domain and application layers free of
framework-specific types.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, ContextManager, Protocol
from uuid import UUID

from src.features.auth.application.types import Principal
from src.features.auth.domain.models import (
    InternalToken,
    Permission,
    RefreshToken,
    Role,
    User,
)


class AuthRefreshTokenTransactionPort(Protocol):
    """Transactional operations used to rotate refresh tokens atomically."""

    def get_refresh_token_for_update(self, token_hash: str) -> RefreshToken | None: ...
    def get_principal(self, user_id: UUID) -> Principal | None: ...
    def create_refresh_token(
        self,
        *,
        user_id: UUID,
        token_hash: str,
        family_id: UUID,
        expires_at: datetime,
        created_ip: str | None,
        user_agent: str | None,
    ) -> RefreshToken: ...
    def revoke_refresh_token(
        self, token_id: UUID, *, replaced_by_token_id: UUID | None = None
    ) -> None: ...
    def revoke_refresh_family(self, family_id: UUID) -> None: ...
    def record_audit_event(
        self,
        *,
        event_type: str,
        user_id: UUID | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None: ...


class AuthRepositoryPort(Protocol):
    """All persistence operations the auth application layer requires."""

    # ── Users ──────────────────────────────────────────────────────────────

    def get_user_by_email(self, email: str) -> User | None: ...
    def get_user_by_id(self, user_id: UUID) -> User | None: ...
    def list_users(self) -> list[User]: ...
    def create_user(self, *, email: str, password_hash: str) -> User | None: ...
    def update_user_login(self, user_id: UUID, when: datetime) -> None: ...
    def set_user_active(self, user_id: UUID, is_active: bool) -> None: ...
    def set_user_verified(self, user_id: UUID) -> None: ...
    def update_user_password(self, user_id: UUID, password_hash: str) -> None: ...
    def increment_user_authz_version(self, user_id: UUID) -> None: ...
    def increment_authz_for_role_users(self, role_id: UUID) -> None: ...
    def get_principal(self, user_id: UUID) -> Principal | None: ...

    # ── Roles ───────────────────────────────────────────────────────────────

    def list_roles(self) -> list[Role]: ...
    def get_role(self, role_id: UUID) -> Role | None: ...
    def get_role_by_name(self, name: str) -> Role | None: ...
    def create_role(
        self, *, name: str, description: str | None = None
    ) -> Role | None: ...
    def update_role(
        self,
        role_id: UUID,
        *,
        name: str | None,
        description: str | None,
        is_active: bool | None,
    ) -> Role | None: ...

    # ── Permissions ─────────────────────────────────────────────────────────

    def list_permissions(self) -> list[Permission]: ...
    def get_permission(self, permission_id: UUID) -> Permission | None: ...
    def get_permission_by_name(self, name: str) -> Permission | None: ...
    def create_permission(
        self, *, name: str, description: str | None = None
    ) -> Permission | None: ...

    # ── Assignments ─────────────────────────────────────────────────────────

    def assign_user_role(self, user_id: UUID, role_id: UUID) -> bool: ...
    def remove_user_role(self, user_id: UUID, role_id: UUID) -> bool: ...
    def assign_role_permission(self, role_id: UUID, permission_id: UUID) -> bool: ...
    def remove_role_permission(self, role_id: UUID, permission_id: UUID) -> bool: ...

    # ── Refresh tokens ───────────────────────────────────────────────────────

    def create_refresh_token(
        self,
        *,
        user_id: UUID,
        token_hash: str,
        family_id: UUID,
        expires_at: datetime,
        created_ip: str | None,
        user_agent: str | None,
    ) -> RefreshToken: ...
    def get_refresh_token_by_hash(self, token_hash: str) -> RefreshToken | None: ...
    def refresh_token_transaction(
        self,
    ) -> ContextManager[AuthRefreshTokenTransactionPort]: ...
    def revoke_refresh_token(
        self, token_id: UUID, *, replaced_by_token_id: UUID | None = None
    ) -> None: ...
    def revoke_refresh_family(self, family_id: UUID) -> None: ...
    def revoke_user_refresh_tokens(self, user_id: UUID) -> None: ...

    # ── Internal tokens ──────────────────────────────────────────────────────

    def create_internal_token(
        self,
        *,
        user_id: UUID | None,
        purpose: str,
        token_hash: str,
        expires_at: datetime,
        created_ip: str | None,
    ) -> InternalToken: ...
    def get_internal_token(
        self, *, token_hash: str, purpose: str
    ) -> InternalToken | None: ...
    def mark_internal_token_used(self, token_id: UUID) -> None: ...

    # ── Audit ────────────────────────────────────────────────────────────────

    def record_audit_event(
        self,
        *,
        event_type: str,
        user_id: UUID | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None: ...

    # ── Lifecycle ────────────────────────────────────────────────────────────

    def close(self) -> None: ...
