"""In-memory ``AuthRepositoryPort`` implementation for unit tests."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterator
from uuid import UUID, uuid4

from src.features.authentication.domain.models import (
    AuditEvent,
    InternalToken,
    RefreshToken,
    User,
)
from src.platform.shared.principal import Principal


def _aware_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class _Stores:
    users: dict[UUID, User] = field(default_factory=dict)
    users_by_email: dict[str, UUID] = field(default_factory=dict)
    refresh_tokens: dict[UUID, RefreshToken] = field(default_factory=dict)
    refresh_token_by_hash: dict[str, UUID] = field(default_factory=dict)
    internal_tokens: dict[UUID, InternalToken] = field(default_factory=dict)
    internal_token_by_hash: dict[tuple[str, str], UUID] = field(default_factory=dict)
    audit_events: list[AuditEvent] = field(default_factory=list)


class FakeAuthRepository:
    """Dict-backed implementation of ``AuthRepositoryPort`` for unit tests."""

    def __init__(self) -> None:
        self._s = _Stores()

    def reset(self) -> None:
        self._s = _Stores()

    def close(self) -> None:
        pass

    # ── User operations ──────────────────────────────────────────────────────

    def get_user_by_email(self, email: str) -> User | None:
        user_id = self._s.users_by_email.get(email)
        return self._s.users.get(user_id) if user_id else None

    def get_user_by_id(self, user_id: UUID) -> User | None:
        return self._s.users.get(user_id)

    def list_users(self, *, limit: int = 100, offset: int = 0) -> list[User]:
        ordered = sorted(self._s.users.values(), key=lambda u: u.created_at)
        return ordered[offset : offset + limit]

    def create_user(self, *, email: str, password_hash: str) -> User | None:
        if email in self._s.users_by_email:
            return None
        now = _aware_now()
        user = User(
            id=uuid4(),
            email=email,
            password_hash=password_hash,
            is_active=True,
            is_verified=False,
            authz_version=1,
            created_at=now,
            updated_at=now,
            last_login_at=None,
        )
        self._s.users[user.id] = user
        self._s.users_by_email[email] = user.id
        return user

    def update_user_login(self, user_id: UUID, when: datetime) -> None:
        existing = self._s.users.get(user_id)
        if existing is None:
            return
        self._s.users[user_id] = _replace(existing, last_login_at=when, updated_at=when)

    def set_user_active(self, user_id: UUID, is_active: bool) -> None:
        existing = self._s.users.get(user_id)
        if existing is None:
            return
        self._s.users[user_id] = _replace(
            existing, is_active=is_active, updated_at=_aware_now()
        )

    def set_user_verified(self, user_id: UUID) -> None:
        existing = self._s.users.get(user_id)
        if existing is None:
            return
        self._s.users[user_id] = _replace(
            existing, is_verified=True, updated_at=_aware_now()
        )

    def update_user_password(self, user_id: UUID, password_hash: str) -> None:
        existing = self._s.users.get(user_id)
        if existing is None:
            return
        self._s.users[user_id] = _replace(
            existing, password_hash=password_hash, updated_at=_aware_now()
        )

    def increment_user_authz_version(self, user_id: UUID) -> None:
        existing = self._s.users.get(user_id)
        if existing is None:
            return
        self._s.users[user_id] = _replace(
            existing,
            authz_version=existing.authz_version + 1,
            updated_at=_aware_now(),
        )

    def get_principal(self, user_id: UUID) -> Principal | None:
        user = self._s.users.get(user_id)
        if user is None:
            return None
        return Principal(
            user_id=user.id,
            email=user.email,
            is_active=user.is_active,
            is_verified=user.is_verified,
            authz_version=user.authz_version,
        )

    # ── Refresh token operations ─────────────────────────────────────────────

    def create_refresh_token(
        self,
        *,
        user_id: UUID,
        token_hash: str,
        family_id: UUID,
        expires_at: datetime,
        created_ip: str | None,
        user_agent: str | None,
    ) -> RefreshToken:
        token = RefreshToken(
            id=uuid4(),
            user_id=user_id,
            token_hash=token_hash,
            family_id=family_id,
            expires_at=expires_at,
            revoked_at=None,
            replaced_by_token_id=None,
            created_at=_aware_now(),
            created_ip=created_ip,
            user_agent=user_agent,
        )
        self._s.refresh_tokens[token.id] = token
        self._s.refresh_token_by_hash[token_hash] = token.id
        return token

    def get_refresh_token_by_hash(self, token_hash: str) -> RefreshToken | None:
        token_id = self._s.refresh_token_by_hash.get(token_hash)
        return self._s.refresh_tokens.get(token_id) if token_id else None

    def revoke_refresh_token(
        self, token_id: UUID, *, replaced_by_token_id: UUID | None = None
    ) -> None:
        existing = self._s.refresh_tokens.get(token_id)
        if existing is None or existing.revoked_at is not None:
            return
        self._s.refresh_tokens[token_id] = _replace(
            existing,
            revoked_at=_aware_now(),
            replaced_by_token_id=replaced_by_token_id,
        )

    def revoke_refresh_family(self, family_id: UUID) -> None:
        for token_id, token in list(self._s.refresh_tokens.items()):
            if token.family_id == family_id and token.revoked_at is None:
                self._s.refresh_tokens[token_id] = _replace(
                    token, revoked_at=_aware_now()
                )

    def revoke_user_refresh_tokens(self, user_id: UUID) -> None:
        for token_id, token in list(self._s.refresh_tokens.items()):
            if token.user_id == user_id and token.revoked_at is None:
                self._s.refresh_tokens[token_id] = _replace(
                    token, revoked_at=_aware_now()
                )

    @contextmanager
    def refresh_token_transaction(self) -> Iterator["FakeAuthRepository"]:
        # Single-process fake — no real transaction semantics needed.
        yield self

    @contextmanager
    def internal_token_transaction(self) -> Iterator["FakeAuthRepository"]:
        yield self

    # Methods consumed by the transaction port (the fake itself plays the role
    # of the transactional context for both refresh-token and internal-token
    # transactions).

    def get_refresh_token_for_update(self, token_hash: str) -> RefreshToken | None:
        return self.get_refresh_token_by_hash(token_hash)

    # ── Internal token operations ────────────────────────────────────────────

    def create_internal_token(
        self,
        *,
        user_id: UUID | None,
        purpose: str,
        token_hash: str,
        expires_at: datetime,
        created_ip: str | None,
    ) -> InternalToken:
        token = InternalToken(
            id=uuid4(),
            user_id=user_id,
            purpose=purpose,
            token_hash=token_hash,
            expires_at=expires_at,
            used_at=None,
            created_at=_aware_now(),
            created_ip=created_ip,
        )
        self._s.internal_tokens[token.id] = token
        self._s.internal_token_by_hash[(token_hash, purpose)] = token.id
        return token

    def get_internal_token(
        self, *, token_hash: str, purpose: str
    ) -> InternalToken | None:
        token_id = self._s.internal_token_by_hash.get((token_hash, purpose))
        return self._s.internal_tokens.get(token_id) if token_id else None

    def get_internal_token_for_update(
        self, *, token_hash: str, purpose: str
    ) -> InternalToken | None:
        return self.get_internal_token(token_hash=token_hash, purpose=purpose)

    def mark_internal_token_used(self, token_id: UUID) -> None:
        existing = self._s.internal_tokens.get(token_id)
        if existing is None:
            return
        self._s.internal_tokens[token_id] = _replace(existing, used_at=_aware_now())

    # ── Audit operations ─────────────────────────────────────────────────────

    def record_audit_event(
        self,
        *,
        event_type: str,
        user_id: UUID | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self._s.audit_events.append(
            AuditEvent(
                id=uuid4(),
                user_id=user_id,
                event_type=event_type,
                metadata=metadata or {},
                created_at=_aware_now(),
                ip_address=ip_address,
                user_agent=user_agent,
            )
        )

    def list_audit_events(
        self,
        *,
        user_id: UUID | None = None,
        event_type: str | None = None,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[AuditEvent]:
        events = self._s.audit_events
        if user_id is not None:
            events = [e for e in events if e.user_id == user_id]
        if event_type is not None:
            events = [e for e in events if e.event_type == event_type]
        if since is not None:
            events = [e for e in events if e.created_at >= since]
        return list(reversed(events))[:limit]

    # ── Test helpers ─────────────────────────────────────────────────────────

    @property
    def stored_users(self) -> dict[UUID, User]:
        return self._s.users

    @property
    def stored_refresh_tokens(self) -> dict[UUID, RefreshToken]:
        return self._s.refresh_tokens

    @property
    def stored_audit_events(self) -> list[AuditEvent]:
        return list(self._s.audit_events)


def _replace(user: Any, **changes: Any) -> Any:
    """Create a new frozen-dataclass instance with selected fields replaced."""
    from dataclasses import replace

    return replace(user, **changes)
