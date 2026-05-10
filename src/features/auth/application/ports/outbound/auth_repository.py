"""Outbound port protocols for auth persistence.

The application layer depends on these protocols, never on the concrete
SQLModel adapter, keeping domain and application layers free of
framework-specific types.

Sub-protocols follow the Interface Segregation Principle — each service
declares only the slice of persistence it actually uses:

  Auth use cases  → UserRepositoryPort + TokenRepositoryPort + AuditRepositoryPort

``AuthRepositoryPort`` is the full composite used by the concrete adapter and
the container; it inherits all sub-protocols so the existing wiring is unchanged.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, ContextManager, Protocol
from uuid import UUID

from src.features.auth.domain.models import (
    AuditEvent,
    InternalToken,
    RefreshToken,
    User,
)
from src.platform.shared.principal import Principal

# ── Transaction protocols ─────────────────────────────────────────────────────


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


class AuthInternalTokenTransactionPort(Protocol):
    """Transactional operations used to consume internal tokens atomically."""

    def get_internal_token_for_update(
        self, *, token_hash: str, purpose: str
    ) -> InternalToken | None: ...
    def update_user_password(self, user_id: UUID, password_hash: str) -> None: ...
    def mark_internal_token_used(self, token_id: UUID) -> None: ...
    def revoke_user_refresh_tokens(self, user_id: UUID) -> None: ...
    def record_audit_event(
        self,
        *,
        event_type: str,
        user_id: UUID | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None: ...


# ── Sub-protocols (ISP slices) ────────────────────────────────────────────────


class UserRepositoryPort(Protocol):
    """Persistence operations scoped to the User aggregate."""

    def get_user_by_email(self, email: str) -> User | None: ...
    def get_user_by_id(self, user_id: UUID) -> User | None: ...
    def list_users(self, *, limit: int = 100, offset: int = 0) -> list[User]: ...
    def create_user(self, *, email: str, password_hash: str) -> User | None: ...
    def update_user_login(self, user_id: UUID, when: datetime) -> None: ...
    def set_user_active(self, user_id: UUID, is_active: bool) -> None: ...
    def set_user_verified(self, user_id: UUID) -> None: ...
    def update_user_password(self, user_id: UUID, password_hash: str) -> None: ...
    def increment_user_authz_version(self, user_id: UUID) -> None: ...
    def get_principal(self, user_id: UUID) -> Principal | None: ...


class TokenRepositoryPort(Protocol):
    """Persistence operations for refresh tokens and single-use internal tokens."""

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
    def internal_token_transaction(
        self,
    ) -> ContextManager[AuthInternalTokenTransactionPort]: ...
    def revoke_refresh_token(
        self, token_id: UUID, *, replaced_by_token_id: UUID | None = None
    ) -> None: ...
    def revoke_refresh_family(self, family_id: UUID) -> None: ...
    def revoke_user_refresh_tokens(self, user_id: UUID) -> None: ...
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


class AuditRepositoryPort(Protocol):
    """Persistence operations for the audit event log."""

    def record_audit_event(
        self,
        *,
        event_type: str,
        user_id: UUID | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None: ...
    def list_audit_events(
        self,
        *,
        user_id: UUID | None = None,
        event_type: str | None = None,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[AuditEvent]: ...


# ── Composite port (used by the concrete adapter and AuthContainer) ────────────


class AuthRepositoryPort(
    UserRepositoryPort,
    TokenRepositoryPort,
    AuditRepositoryPort,
    Protocol,
):
    """Full persistence surface for the auth feature.

    Inherits all sub-protocols. The concrete ``SQLModelAuthRepository``
    implements this combined interface; services may accept narrower
    sub-protocol types when that improves testability.
    """

    def close(self) -> None: ...
