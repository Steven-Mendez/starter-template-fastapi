"""In-memory ``AuthRepositoryPort`` implementation for unit tests."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol, runtime_checkable
from uuid import UUID, uuid4

from app_platform.shared.result import Result
from features.authentication.domain.models import (
    AuditEvent,
    Credential,
    InternalToken,
    RefreshToken,
)
from features.users.application.errors import UserError
from features.users.domain.user import User


def _aware_now() -> datetime:
    return datetime.now(UTC)


@dataclass(slots=True)
class _Stores:
    refresh_tokens: dict[UUID, RefreshToken] = field(default_factory=dict)
    refresh_token_by_hash: dict[str, UUID] = field(default_factory=dict)
    internal_tokens: dict[UUID, InternalToken] = field(default_factory=dict)
    internal_token_by_hash: dict[tuple[str, str], UUID] = field(default_factory=dict)
    audit_events: list[AuditEvent] = field(default_factory=list)
    credentials: dict[tuple[UUID, str], Credential] = field(default_factory=dict)


class FakeAuthRepository:
    """Dict-backed implementation of ``AuthRepositoryPort`` for unit tests."""

    def __init__(self) -> None:
        self._s = _Stores()
        # Optional session-scoped user writer the in-transaction wrappers
        # delegate to (``upsert_credential`` and ``mark_user_verified``
        # for confirm-style use cases; ``create_user`` for registration).
        # Tests that exercise the cross-feature transactional path attach
        # a ``FakeUserPort`` here; tests that only touch the auth half
        # leave it as ``None``.
        self._user_writer: _FakeUserWriter | None = None

    def reset(self) -> None:
        self._s = _Stores()

    def close(self) -> None:
        pass

    def attach_user_writer(self, writer: _FakeUserWriter) -> None:
        """Bind a ``UserPort``-shaped writer so cross-feature UoWs work.

        The real SQLModel adapter receives this binding via a
        ``user_writer_factory`` argument; the fake takes the writer
        directly because there is no session to scope it to.
        """
        self._user_writer = writer

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
    def refresh_token_transaction(self) -> Iterator[FakeAuthRepository]:
        # Single-process fake — no real transaction semantics needed.
        yield self

    @contextmanager
    def internal_token_transaction(self) -> Iterator[_FakeInternalTokenTx]:
        """Yield a wrapper that bundles token + credential + user-row writes.

        The real SQLModel adapter exposes ``upsert_credential``,
        ``mark_user_verified``, and ``bump_user_authz_version`` on the
        in-transaction writer so confirm-style use cases run their full
        state change inside one transaction. The fake mirrors that
        surface by delegating to the attached ``user_writer`` for the
        user-row methods (``mark_verified`` / ``bump_authz_version``)
        and to the repository's own dict-backed stores for everything
        else.

        Snapshots both stores on entry and restores them on exception
        so confirm-style unit tests can assert rollback semantics
        without a real DB.
        """
        auth_snapshot = _snapshot_stores(self._s)
        user_snapshot = (
            _snapshot_user_writer(self._user_writer)
            if self._user_writer is not None
            else None
        )
        try:
            yield _FakeInternalTokenTx(self, self._user_writer)
        except BaseException:
            _restore_stores(self._s, auth_snapshot)
            if self._user_writer is not None and user_snapshot is not None:
                _restore_user_writer(self._user_writer, user_snapshot)
            raise

    @contextmanager
    def register_user_transaction(self) -> Iterator[_FakeRegisterUserTx]:
        """Yield a writer covering the three registration writes.

        Mirrors the SQLModel adapter's ``register_user_transaction``:
        the writer exposes ``create_user``, ``upsert_credential``, and
        ``record_audit_event`` on the same logical transaction.
        ``create_user`` is delegated to the attached user writer.

        On exception the fake snapshots both the auth-side stores and
        the attached user writer's internal state and restores them so
        the unit tests can observe transactional rollback semantics
        without a real DB. The snapshot is shallow but adequate for
        the dict-backed fakes (``FakeAuthRepository`` /
        ``FakeUserPort``) used in the auth unit suite.
        """
        if self._user_writer is None:
            raise RuntimeError(
                "FakeAuthRepository.register_user_transaction was called "
                "without an attached user writer. Call "
                "attach_user_writer(...) with a FakeUserPort (or any "
                "object satisfying _FakeUserWriter) before exercising "
                "the registration use case."
            )
        auth_snapshot = _snapshot_stores(self._s)
        user_snapshot = _snapshot_user_writer(self._user_writer)
        try:
            yield _FakeRegisterUserTx(self, self._user_writer)
        except BaseException:
            _restore_stores(self._s, auth_snapshot)
            _restore_user_writer(self._user_writer, user_snapshot)
            raise

    @contextmanager
    def issue_internal_token_transaction(self) -> Iterator[_FakeIssueTokenTx]:
        """Yield a thin wrapper that exposes ``outbox`` alongside the writes.

        The wrapper's ``outbox`` is an :class:`InlineDispatchOutboxAdapter`
        with a no-op dispatcher; unit tests that need to assert outbox
        behaviour install their own adapter on the fake before
        exercising the use case.
        """
        from features.outbox.tests.fakes.fake_outbox import (
            InlineDispatchOutboxAdapter,
        )

        outbox = getattr(
            self,
            "_issue_outbox_override",
            InlineDispatchOutboxAdapter(dispatcher=lambda _n, _p: None),
        )
        yield _FakeIssueTokenTx(self, outbox)

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

    def invalidate_unused_tokens_for(self, user_id: UUID, purpose: str) -> int:
        """Stamp ``used_at`` on every unused token for ``(user_id, purpose)``."""
        now = _aware_now()
        updated = 0
        for token_id, token in list(self._s.internal_tokens.items()):
            if (
                token.user_id == user_id
                and token.purpose == purpose
                and token.used_at is None
            ):
                self._s.internal_tokens[token_id] = _replace(token, used_at=now)
                updated += 1
        return updated

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

    # ── Maintenance operations ───────────────────────────────────────────────

    def delete_expired_refresh_tokens(self, cutoff: datetime) -> int:
        """In-memory equivalent of the SQLModel batched delete.

        A row is eligible when either ``expires_at < cutoff`` or
        ``revoked_at < cutoff`` (the same predicate the real adapter
        runs). The fake skips the 10k batching the real implementation
        uses because the in-memory store is bounded by the test setup.
        """
        eligible = [
            token_id
            for token_id, token in self._s.refresh_tokens.items()
            if token.expires_at < cutoff
            or (token.revoked_at is not None and token.revoked_at < cutoff)
        ]
        for token_id in eligible:
            del self._s.refresh_tokens[token_id]
        return len(eligible)

    def delete_expired_internal_tokens(self, cutoff: datetime) -> int:
        """In-memory equivalent of the SQLModel batched delete.

        A row is eligible when either ``used_at < cutoff`` or
        ``expires_at < cutoff``.
        """
        eligible = [
            token_id
            for token_id, token in self._s.internal_tokens.items()
            if (token.used_at is not None and token.used_at < cutoff)
            or token.expires_at < cutoff
        ]
        for token_id in eligible:
            del self._s.internal_tokens[token_id]
        return len(eligible)

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
        before: tuple[datetime, UUID] | None = None,
        limit: int = 100,
    ) -> list[AuditEvent]:
        events = self._s.audit_events
        if user_id is not None:
            events = [e for e in events if e.user_id == user_id]
        if event_type is not None:
            events = [e for e in events if e.event_type == event_type]
        if since is not None:
            events = [e for e in events if e.created_at >= since]
        ordered = sorted(events, key=lambda e: (e.created_at, e.id), reverse=True)
        if before is not None:
            ordered = [e for e in ordered if (e.created_at, e.id) < before]
        return ordered[:limit]

    # ── Credential operations ────────────────────────────────────────────────

    def get_credential_for_user(
        self, user_id: UUID, *, algorithm: str = "argon2"
    ) -> Credential | None:
        return self._s.credentials.get((user_id, algorithm))

    def upsert_credential(
        self, *, user_id: UUID, algorithm: str, hash: str
    ) -> Credential:
        now = _aware_now()
        existing = self._s.credentials.get((user_id, algorithm))
        if existing is None:
            credential = Credential(
                id=uuid4(),
                user_id=user_id,
                algorithm=algorithm,
                hash=hash,
                last_changed_at=now,
                created_at=now,
            )
        else:
            credential = _replace(existing, hash=hash, last_changed_at=now)
        self._s.credentials[(user_id, algorithm)] = credential
        return credential

    # ── Test helpers ─────────────────────────────────────────────────────────

    @property
    def stored_refresh_tokens(self) -> dict[UUID, RefreshToken]:
        return self._s.refresh_tokens

    @property
    def stored_audit_events(self) -> list[AuditEvent]:
        return list(self._s.audit_events)


def _replace(obj: Any, **changes: Any) -> Any:
    """Create a new frozen-dataclass instance with selected fields replaced."""
    from dataclasses import replace

    return replace(obj, **changes)


def _snapshot_stores(stores: _Stores) -> _Stores:
    """Shallow-copy each container inside ``stores`` for rollback semantics.

    The stored values (``RefreshToken`` / ``InternalToken`` / ``Credential`` /
    ``AuditEvent``) are frozen dataclasses so a shallow copy of each dict
    or list is sufficient — the values are immutable.
    """
    return _Stores(
        refresh_tokens=dict(stores.refresh_tokens),
        refresh_token_by_hash=dict(stores.refresh_token_by_hash),
        internal_tokens=dict(stores.internal_tokens),
        internal_token_by_hash=dict(stores.internal_token_by_hash),
        audit_events=list(stores.audit_events),
        credentials=dict(stores.credentials),
    )


def _restore_stores(target: _Stores, snapshot: _Stores) -> None:
    """Mutate ``target`` in place to match ``snapshot``.

    Used by the rollback paths instead of rebinding ``self._s`` so any
    other reference (e.g. a wrapping fake that shares the same
    ``_Stores`` instance) sees the rollback. The frozen-dataclass
    values inside the containers don't need to be copied — only the
    containers themselves.
    """
    target.refresh_tokens.clear()
    target.refresh_tokens.update(snapshot.refresh_tokens)
    target.refresh_token_by_hash.clear()
    target.refresh_token_by_hash.update(snapshot.refresh_token_by_hash)
    target.internal_tokens.clear()
    target.internal_tokens.update(snapshot.internal_tokens)
    target.internal_token_by_hash.clear()
    target.internal_token_by_hash.update(snapshot.internal_token_by_hash)
    target.audit_events[:] = snapshot.audit_events
    target.credentials.clear()
    target.credentials.update(snapshot.credentials)


def _snapshot_user_writer(writer: Any) -> Any:
    """Capture the internal state of a dict-backed user writer.

    The auth unit suite uses ``FakeUserPort`` which keeps state in a
    private ``_s`` ``_Stores`` mirror. The snapshot is a tuple of
    shallow-copied dicts; ``_restore_user_writer`` swaps them back on
    rollback. Writers that do not expose ``_s`` (custom test doubles)
    are recorded as ``None`` and the restore call is a no-op.
    """
    inner = getattr(writer, "_s", None)
    if inner is None:
        return None
    return (dict(inner.users), dict(inner.users_by_email))


def _restore_user_writer(writer: Any, snapshot: Any) -> None:
    inner = getattr(writer, "_s", None)
    if inner is None or snapshot is None:
        return
    users_dict, users_by_email = snapshot
    inner.users.clear()
    inner.users.update(users_dict)
    inner.users_by_email.clear()
    inner.users_by_email.update(users_by_email)


@runtime_checkable
class _FakeUserWriter(Protocol):
    """Structural type for the session-bound user writer the fake calls.

    Any object exposing ``create(email=...)``, ``mark_verified(user_id)``,
    and ``bump_authz_version(user_id)`` satisfies the contract.
    ``FakeUserPort`` already does, and the real
    ``SessionSQLModelUserRepository`` likewise.
    """

    def create(self, *, email: str) -> Result[User, UserError]: ...

    def mark_verified(self, user_id: UUID) -> None: ...

    def bump_authz_version(self, user_id: UUID) -> None: ...


class _FakeRegisterUserTx:
    """In-memory stand-in for the session-scoped registration writer."""

    def __init__(self, repo: FakeAuthRepository, user_writer: _FakeUserWriter) -> None:
        self._repo = repo
        self._user_writer = user_writer

    def create_user(self, *, email: str) -> Result[User, UserError]:
        return self._user_writer.create(email=email)

    def upsert_credential(
        self, *, user_id: UUID, algorithm: str, hash: str
    ) -> Credential:
        return self._repo.upsert_credential(
            user_id=user_id, algorithm=algorithm, hash=hash
        )

    def record_audit_event(
        self,
        *,
        event_type: str,
        user_id: UUID | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self._repo.record_audit_event(
            event_type=event_type,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            metadata=metadata,
        )


class _FakeInternalTokenTx:
    """In-memory stand-in for the session-scoped internal-token writer."""

    def __init__(
        self,
        repo: FakeAuthRepository,
        user_writer: _FakeUserWriter | None,
    ) -> None:
        self._repo = repo
        self._user_writer = user_writer

    def get_internal_token_for_update(
        self, *, token_hash: str, purpose: str
    ) -> InternalToken | None:
        return self._repo.get_internal_token_for_update(
            token_hash=token_hash, purpose=purpose
        )

    def mark_internal_token_used(self, token_id: UUID) -> None:
        self._repo.mark_internal_token_used(token_id)

    def revoke_user_refresh_tokens(self, user_id: UUID) -> None:
        self._repo.revoke_user_refresh_tokens(user_id)

    def upsert_credential(
        self, *, user_id: UUID, algorithm: str, hash: str
    ) -> Credential:
        return self._repo.upsert_credential(
            user_id=user_id, algorithm=algorithm, hash=hash
        )

    def mark_user_verified(self, user_id: UUID) -> None:
        if self._user_writer is None:
            raise RuntimeError(
                "FakeAuthRepository.internal_token_transaction was opened "
                "without an attached user writer; mark_user_verified is "
                "unavailable. Call attach_user_writer(...) on the fake "
                "before exercising confirm-style use cases."
            )
        self._user_writer.mark_verified(user_id)

    def bump_user_authz_version(self, user_id: UUID) -> None:
        if self._user_writer is None:
            raise RuntimeError(
                "FakeAuthRepository.internal_token_transaction was opened "
                "without an attached user writer; bump_user_authz_version "
                "is unavailable. Call attach_user_writer(...) on the fake."
            )
        self._user_writer.bump_authz_version(user_id)

    def record_audit_event(
        self,
        *,
        event_type: str,
        user_id: UUID | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self._repo.record_audit_event(
            event_type=event_type,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            metadata=metadata,
        )


class _FakeIssueTokenTx:
    """Test stand-in for the session-scoped issue-token transaction.

    Forwards token + audit writes to the underlying fake repository
    and exposes ``outbox`` as the configured (or default) adapter.
    """

    def __init__(self, repo: FakeAuthRepository, outbox: Any) -> None:
        self._repo = repo
        self.outbox = outbox

    def create_internal_token(
        self,
        *,
        user_id: UUID | None,
        purpose: str,
        token_hash: str,
        expires_at: datetime,
        created_ip: str | None,
    ) -> InternalToken:
        return self._repo.create_internal_token(
            user_id=user_id,
            purpose=purpose,
            token_hash=token_hash,
            expires_at=expires_at,
            created_ip=created_ip,
        )

    def invalidate_unused_tokens_for(self, user_id: UUID, purpose: str) -> int:
        return self._repo.invalidate_unused_tokens_for(user_id, purpose)

    def record_audit_event(
        self,
        *,
        event_type: str,
        user_id: UUID | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self._repo.record_audit_event(
            event_type=event_type,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            metadata=metadata,
        )
