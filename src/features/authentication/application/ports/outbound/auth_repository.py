"""Outbound port protocols for authentication persistence.

After the users feature extraction, the authentication feature owns
only credentials- and session-shaped state: refresh tokens, single-use
internal tokens, and the audit log. The ``User`` entity lives in the
users feature and is reached through :class:`UserPort`.
"""

from __future__ import annotations

from contextlib import AbstractContextManager
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from features.authentication.domain.models import (
    AuditEvent,
    Credential,
    InternalToken,
    RefreshToken,
)
from features.outbox.application.ports.outbox_port import OutboxPort


class AuthRefreshTokenTransactionPort(Protocol):
    """Transactional operations used to rotate refresh tokens atomically."""

    def get_refresh_token_for_update(self, token_hash: str) -> RefreshToken | None: ...
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


class AuthIssueTokenTransactionPort(Protocol):
    """Issue a single-use internal token and stage its side effects atomically.

    The :attr:`outbox` adapter is bound to the same session as the token
    insert and the audit event, so the row that the relay later
    dispatches is committed in the same transaction as the token row —
    if the use case rolls back, the relay never sees the outbox row.
    """

    outbox: OutboxPort

    def create_internal_token(
        self,
        *,
        user_id: UUID | None,
        purpose: str,
        token_hash: str,
        expires_at: datetime,
        created_ip: str | None,
    ) -> InternalToken: ...

    def invalidate_unused_tokens_for(self, user_id: UUID, purpose: str) -> int: ...

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
    ) -> AbstractContextManager[AuthRefreshTokenTransactionPort]: ...
    def internal_token_transaction(
        self,
    ) -> AbstractContextManager[AuthInternalTokenTransactionPort]: ...
    def issue_internal_token_transaction(
        self,
    ) -> AbstractContextManager[AuthIssueTokenTransactionPort]: ...
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


class CredentialRepositoryPort(Protocol):
    """Persistence operations for password credentials."""

    def get_credential_for_user(
        self, user_id: UUID, *, algorithm: str = "argon2"
    ) -> Credential | None: ...
    def upsert_credential(
        self, *, user_id: UUID, algorithm: str, hash: str
    ) -> Credential: ...


class AuthRepositoryPort(
    TokenRepositoryPort,
    AuditRepositoryPort,
    CredentialRepositoryPort,
    Protocol,
):
    """Full persistence surface for the authentication feature.

    Inherits all sub-protocols. The concrete ``SQLModelAuthRepository``
    implements this combined interface; services may accept narrower
    sub-protocol types when that improves testability.
    """

    def close(self) -> None: ...
