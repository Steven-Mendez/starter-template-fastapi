"""SQLModel-backed repository for the authentication feature.

Owns every read and write against the authentication schema (refresh
tokens, single-use internal tokens, audit log). The ``users`` table is
owned by the users feature and reached through :class:`UserPort`; this
module never imports ``UserTable``.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from types import TracebackType
from typing import Any, Self, cast, overload
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import update
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine, select

from features.authentication.adapters.outbound.persistence.sqlmodel.models import (
    AuthAuditEventTable,
    AuthInternalTokenTable,
    CredentialTable,
    RefreshTokenTable,
    utc_now,
)
from features.authentication.domain.models import (
    AuditEvent,
    Credential,
    InternalToken,
    RefreshToken,
)
from features.outbox.application.ports.outbox_port import OutboxPort
from features.outbox.application.ports.outbox_uow_port import OutboxUnitOfWorkPort


@overload
def _ensure_utc(value: datetime) -> datetime: ...
@overload
def _ensure_utc(value: None) -> None: ...
def _ensure_utc(value: datetime | None) -> datetime | None:
    """Single boundary for tzinfo coercion at the persistence boundary."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _to_refresh_token(row: RefreshTokenTable) -> RefreshToken:
    return RefreshToken(
        id=row.id,
        user_id=row.user_id,
        token_hash=row.token_hash,
        family_id=row.family_id,
        expires_at=_ensure_utc(row.expires_at),
        revoked_at=_ensure_utc(row.revoked_at),
        replaced_by_token_id=row.replaced_by_token_id,
        created_at=_ensure_utc(row.created_at),
        created_ip=row.created_ip,
        user_agent=row.user_agent,
    )


def _to_internal_token(row: AuthInternalTokenTable) -> InternalToken:
    return InternalToken(
        id=row.id,
        user_id=row.user_id,
        purpose=row.purpose,
        token_hash=row.token_hash,
        expires_at=_ensure_utc(row.expires_at),
        used_at=_ensure_utc(row.used_at),
        created_at=_ensure_utc(row.created_at),
        created_ip=row.created_ip,
    )


def _to_credential(row: CredentialTable) -> Credential:
    return Credential(
        id=row.id,
        user_id=row.user_id,
        algorithm=row.algorithm,
        hash=row.hash,
        last_changed_at=_ensure_utc(row.last_changed_at),
        created_at=_ensure_utc(row.created_at),
    )


def _to_audit_event(row: AuthAuditEventTable) -> AuditEvent:
    return AuditEvent(
        id=row.id,
        user_id=row.user_id,
        event_type=row.event_type,
        metadata=row.event_metadata,
        created_at=_ensure_utc(row.created_at),
        ip_address=row.ip_address,
        user_agent=row.user_agent,
    )


class _SessionRefreshTokenTransaction:
    """Session-bound refresh-token operations used inside one DB transaction."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_refresh_token_for_update(self, token_hash: str) -> RefreshToken | None:
        row = self._session.exec(
            select(RefreshTokenTable)
            .where(RefreshTokenTable.token_hash == token_hash)
            .with_for_update()
        ).one_or_none()
        return _to_refresh_token(row) if row is not None else None

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
        existing_user_id = self._session.exec(
            select(RefreshTokenTable.user_id)
            .where(RefreshTokenTable.family_id == family_id)
            .limit(1)
        ).one_or_none()
        if existing_user_id is not None and existing_user_id != user_id:
            raise ValueError(
                f"refresh token family {family_id} belongs to a different user"
            )
        refresh = RefreshTokenTable(
            user_id=user_id,
            token_hash=token_hash,
            family_id=family_id,
            expires_at=expires_at,
            created_ip=created_ip,
            user_agent=user_agent,
        )
        self._session.add(refresh)
        self._session.flush()
        self._session.refresh(refresh)
        return _to_refresh_token(refresh)

    def revoke_refresh_token(
        self, token_id: UUID, *, replaced_by_token_id: UUID | None = None
    ) -> None:
        token = self._session.get(RefreshTokenTable, token_id)
        if token is None:
            return
        token.revoked_at = token.revoked_at or utc_now()
        token.replaced_by_token_id = replaced_by_token_id
        self._session.add(token)

    def revoke_refresh_family(self, family_id: UUID) -> None:
        tokens = self._session.exec(
            select(RefreshTokenTable)
            .where(RefreshTokenTable.family_id == family_id)
            .with_for_update()
        ).all()
        now = utc_now()
        for token in tokens:
            token.revoked_at = token.revoked_at or now
            self._session.add(token)

    def record_audit_event(
        self,
        *,
        event_type: str,
        user_id: UUID | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self._session.add(
            AuthAuditEventTable(
                user_id=user_id,
                event_type=event_type,
                ip_address=ip_address,
                user_agent=user_agent,
                event_metadata=metadata or {},
            )
        )


class _SessionInternalTokenTransaction:
    """Session-bound internal-token operations used inside one DB transaction."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_internal_token_for_update(
        self, *, token_hash: str, purpose: str
    ) -> InternalToken | None:
        row = self._session.exec(
            select(AuthInternalTokenTable)
            .where(
                AuthInternalTokenTable.token_hash == token_hash,
                AuthInternalTokenTable.purpose == purpose,
            )
            .with_for_update()
        ).one_or_none()
        return _to_internal_token(row) if row is not None else None

    def mark_internal_token_used(self, token_id: UUID) -> None:
        token = self._session.get(AuthInternalTokenTable, token_id)
        if token is None:
            return
        token.used_at = token.used_at or utc_now()
        self._session.add(token)

    def revoke_user_refresh_tokens(self, user_id: UUID) -> None:
        tokens = self._session.exec(
            select(RefreshTokenTable).where(
                cast(Any, RefreshTokenTable.user_id == user_id),
                cast(Any, RefreshTokenTable.revoked_at).is_(None),
            )
        ).all()
        now = utc_now()
        for token in tokens:
            token.revoked_at = now
            self._session.add(token)

    def record_audit_event(
        self,
        *,
        event_type: str,
        user_id: UUID | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self._session.add(
            AuthAuditEventTable(
                user_id=user_id,
                event_type=event_type,
                ip_address=ip_address,
                user_agent=user_agent,
                event_metadata=metadata or {},
            )
        )


class _SessionIssueTokenTransaction:
    """Issue a single-use internal token + outbox row in one DB transaction.

    Used by request-path producer use cases (``RequestPasswordReset``,
    ``RequestEmailVerification``) so the token insert, the audit event,
    and the side-effect intent commit atomically. The ``outbox``
    attribute is a session-scoped writer bound to the same session as
    the token write.
    """

    def __init__(self, session: Session, outbox: OutboxPort) -> None:
        self._session = session
        # The yielded writer satisfies ``OutboxPort.enqueue(...)``; we
        # keep the typed attribute name producer code uses today.
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
        token = AuthInternalTokenTable(
            user_id=user_id,
            purpose=purpose,
            token_hash=token_hash,
            expires_at=expires_at,
            created_ip=created_ip,
        )
        self._session.add(token)
        self._session.flush()
        self._session.refresh(token)
        return _to_internal_token(token)

    def invalidate_unused_tokens_for(self, user_id: UUID, purpose: str) -> int:
        """Stamp ``used_at = now()`` on every prior unused token for the pair.

        Returns the number of rows updated. Runs inside the same session
        as the subsequent ``create_internal_token`` call, so the
        invalidation and the new token insert commit atomically (or roll
        back atomically).
        """
        # ``synchronize_session=False`` avoids fetching matching rows
        # just to expire them in the identity map — this writer is
        # always followed by an insert and a commit, so there is no need
        # to reconcile in-memory ORM state.
        result = self._session.exec(
            update(AuthInternalTokenTable)
            .where(
                cast(Any, AuthInternalTokenTable.user_id) == user_id,
                cast(Any, AuthInternalTokenTable.purpose) == purpose,
                cast(Any, AuthInternalTokenTable.used_at).is_(None),
            )
            .values(used_at=utc_now())
            .execution_options(synchronize_session=False)
        )
        return int(result.rowcount or 0)

    def record_audit_event(
        self,
        *,
        event_type: str,
        user_id: UUID | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self._session.add(
            AuthAuditEventTable(
                user_id=user_id,
                event_type=event_type,
                ip_address=ip_address,
                user_agent=user_agent,
                event_metadata=metadata or {},
            )
        )


class SQLModelAuthRepository:
    """SQLModel-backed persistence adapter for authentication state.

    Provides a synchronous, session-scoped interface for refresh tokens,
    internal tokens, and audit events. Refresh-token rotation and
    internal-token consumption open a single transaction so the lock,
    rotate, revoke, and audit writes commit or roll back together.
    """

    def __init__(
        self,
        database_url: str,
        *,
        create_schema: bool = False,
        pool_size: int = 5,
        max_overflow: int = 10,
        pool_recycle: int = 1800,
        pool_pre_ping: bool = True,
        outbox_uow: OutboxUnitOfWorkPort | None = None,
    ) -> None:
        if not database_url.startswith("postgresql"):
            msg = "SQLModelAuthRepository supports PostgreSQL DSNs only"
            raise ValueError(msg)
        self._engine = create_engine(
            database_url,
            pool_pre_ping=pool_pre_ping,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_recycle=pool_recycle,
        )
        self._closed = False
        # The composition root passes ``outbox_uow`` so the repository can
        # open atomic token-+-outbox transactions. Kept optional so
        # existing tests that do not exercise the outbox path can still
        # construct the repository with just a DSN.
        self._outbox_uow: OutboxUnitOfWorkPort | None = outbox_uow
        if create_schema:
            SQLModel.metadata.create_all(self._engine)

    @classmethod
    def from_engine(
        cls,
        engine: Engine,
        *,
        create_schema: bool = False,
        outbox_uow: OutboxUnitOfWorkPort | None = None,
    ) -> SQLModelAuthRepository:
        instance = cls.__new__(cls)
        instance._engine = engine
        instance._closed = False
        instance._outbox_uow = outbox_uow
        if create_schema:
            SQLModel.metadata.create_all(engine)
        return instance

    @property
    def engine(self) -> Engine:
        return self._engine

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        del exc_type, exc, tb
        self.close()

    def close(self) -> None:
        if self._closed:
            return
        self._engine.dispose()
        self._closed = True

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("SQLModelAuthRepository is closed")

    @contextmanager
    def _session_scope(self) -> Iterator[Session]:
        self._ensure_open()
        with Session(self._engine, expire_on_commit=False) as session:
            yield session

    @contextmanager
    def _write_session_scope(self) -> Iterator[Session]:
        self._ensure_open()
        with Session(self._engine, expire_on_commit=False) as session:
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise

    @contextmanager
    def refresh_token_transaction(self) -> Iterator[_SessionRefreshTokenTransaction]:
        self._ensure_open()
        with Session(self._engine, expire_on_commit=False) as session:
            try:
                yield _SessionRefreshTokenTransaction(session)
                session.commit()
            except Exception:
                session.rollback()
                raise

    @contextmanager
    def internal_token_transaction(self) -> Iterator[_SessionInternalTokenTransaction]:
        self._ensure_open()
        with Session(self._engine, expire_on_commit=False) as session:
            try:
                yield _SessionInternalTokenTransaction(session)
                session.commit()
            except Exception:
                session.rollback()
                raise

    @contextmanager
    def issue_internal_token_transaction(
        self,
    ) -> Iterator[_SessionIssueTokenTransaction]:
        """Open a write transaction that issues a token + outbox row atomically.

        The yielded transaction object exposes ``create_internal_token``
        and ``record_audit_event`` (both staged on the session) and an
        ``outbox`` attribute bound to the same session. Commit happens
        on successful exit; any exception triggers a rollback so the
        outbox row is never visible to the relay if the use case fails.
        """
        self._ensure_open()
        if self._outbox_uow is None:
            raise RuntimeError(
                "SQLModelAuthRepository.issue_internal_token_transaction was "
                "called before an OutboxUnitOfWorkPort was registered. The "
                "composition root must pass ``outbox_uow=`` to the constructor "
                "or to ``from_engine(...)``."
            )
        with self._outbox_uow.transaction() as writer:
            # Outbox writers backed by SQLModel expose the active
            # session so SQLModel-aware producer adapters (this one)
            # can attach their own writes to the same transaction.
            # Producer *composition* still depends only on the
            # ``OutboxUnitOfWorkPort`` Protocol and never sees a
            # ``Session`` type.
            session = getattr(writer, "session", None)
            if isinstance(session, Session):
                yield _SessionIssueTokenTransaction(session, writer)
                return
            # Writers without a shared session (e.g. inline-dispatch
            # fakes used in e2e tests) cannot satisfy the atomic
            # contract; the repository falls back to opening its own
            # session. Atomicity guarantees are exercised against the
            # real SQLModel adapter by the integration suite.
            with Session(self._engine, expire_on_commit=False) as fallback_session:
                try:
                    yield _SessionIssueTokenTransaction(fallback_session, writer)
                    fallback_session.commit()
                except Exception:
                    fallback_session.rollback()
                    raise

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
        with self._write_session_scope() as session:
            existing_user_id = session.exec(
                select(RefreshTokenTable.user_id)
                .where(RefreshTokenTable.family_id == family_id)
                .limit(1)
            ).one_or_none()
            if existing_user_id is not None and existing_user_id != user_id:
                raise ValueError(
                    f"refresh token family {family_id} belongs to a different user"
                )
            refresh = RefreshTokenTable(
                user_id=user_id,
                token_hash=token_hash,
                family_id=family_id,
                expires_at=expires_at,
                created_ip=created_ip,
                user_agent=user_agent,
            )
            session.add(refresh)
            session.flush()
            session.refresh(refresh)
            return _to_refresh_token(refresh)

    def get_refresh_token_by_hash(self, token_hash: str) -> RefreshToken | None:
        with self._session_scope() as session:
            row = session.exec(
                select(RefreshTokenTable).where(
                    RefreshTokenTable.token_hash == token_hash
                )
            ).one_or_none()
            return _to_refresh_token(row) if row is not None else None

    def revoke_refresh_token(
        self, token_id: UUID, *, replaced_by_token_id: UUID | None = None
    ) -> None:
        with self._write_session_scope() as session:
            token = session.get(RefreshTokenTable, token_id)
            if token is None:
                return
            token.revoked_at = token.revoked_at or utc_now()
            token.replaced_by_token_id = replaced_by_token_id
            session.add(token)

    def revoke_refresh_family(self, family_id: UUID) -> None:
        with self._write_session_scope() as session:
            tokens = session.exec(
                select(RefreshTokenTable).where(
                    RefreshTokenTable.family_id == family_id
                )
            ).all()
            now = utc_now()
            for token in tokens:
                token.revoked_at = token.revoked_at or now
                session.add(token)

    def revoke_user_refresh_tokens(self, user_id: UUID) -> None:
        with self._write_session_scope() as session:
            tokens = session.exec(
                select(RefreshTokenTable).where(
                    cast(Any, RefreshTokenTable.user_id == user_id),
                    cast(Any, RefreshTokenTable.revoked_at).is_(None),
                )
            ).all()
            now = utc_now()
            for token in tokens:
                token.revoked_at = now
                session.add(token)

    def create_internal_token(
        self,
        *,
        user_id: UUID | None,
        purpose: str,
        token_hash: str,
        expires_at: datetime,
        created_ip: str | None,
    ) -> InternalToken:
        token = AuthInternalTokenTable(
            user_id=user_id,
            purpose=purpose,
            token_hash=token_hash,
            expires_at=expires_at,
            created_ip=created_ip,
        )
        with self._write_session_scope() as session:
            session.add(token)
            session.flush()
            session.refresh(token)
            return _to_internal_token(token)

    def get_internal_token(
        self, *, token_hash: str, purpose: str
    ) -> InternalToken | None:
        with self._session_scope() as session:
            row = session.exec(
                select(AuthInternalTokenTable).where(
                    AuthInternalTokenTable.token_hash == token_hash,
                    AuthInternalTokenTable.purpose == purpose,
                )
            ).one_or_none()
            return _to_internal_token(row) if row is not None else None

    def mark_internal_token_used(self, token_id: UUID) -> None:
        with self._write_session_scope() as session:
            token = session.get(AuthInternalTokenTable, token_id)
            if token is None:
                return
            token.used_at = token.used_at or utc_now()
            session.add(token)

    def record_audit_event(
        self,
        *,
        event_type: str,
        user_id: UUID | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        event = AuthAuditEventTable(
            user_id=user_id,
            event_type=event_type,
            ip_address=ip_address,
            user_agent=user_agent,
            event_metadata=metadata or {},
        )
        with self._write_session_scope() as session:
            session.add(event)

    def get_credential_for_user(
        self, user_id: UUID, *, algorithm: str = "argon2"
    ) -> Credential | None:
        with self._session_scope() as session:
            row = session.exec(
                select(CredentialTable).where(
                    CredentialTable.user_id == user_id,
                    CredentialTable.algorithm == algorithm,
                )
            ).one_or_none()
            return _to_credential(row) if row is not None else None

    def upsert_credential(
        self, *, user_id: UUID, algorithm: str, hash: str
    ) -> Credential:
        with self._write_session_scope() as session:
            row = session.exec(
                select(CredentialTable)
                .where(
                    CredentialTable.user_id == user_id,
                    CredentialTable.algorithm == algorithm,
                )
                .with_for_update()
            ).one_or_none()
            now = utc_now()
            if row is None:
                row = CredentialTable(
                    user_id=user_id,
                    algorithm=algorithm,
                    hash=hash,
                    last_changed_at=now,
                    created_at=now,
                )
                session.add(row)
            else:
                row.hash = hash
                row.last_changed_at = now
                session.add(row)
            session.flush()
            session.refresh(row)
            return _to_credential(row)

    def list_audit_events(
        self,
        *,
        user_id: UUID | None = None,
        event_type: str | None = None,
        since: datetime | None = None,
        before: tuple[datetime, UUID] | None = None,
        limit: int = 100,
    ) -> list[AuditEvent]:
        """Return audit events ordered newest-first, optionally paginated.

        ``before`` is a ``(created_at, id)`` keyset cursor: when provided
        only rows strictly earlier than the tuple are returned, walking
        the table backwards page by page. The audit-event ``id`` column
        is a UUID (not a monotonic bigserial), so the cursor includes
        ``created_at`` as the primary ordering key and ``id`` only as a
        tiebreaker — identical to the users pagination shape.
        """
        with self._session_scope() as session:
            statement = select(AuthAuditEventTable)
            if user_id is not None:
                statement = statement.where(AuthAuditEventTable.user_id == user_id)
            if event_type is not None:
                statement = statement.where(
                    AuthAuditEventTable.event_type == event_type
                )
            if since is not None:
                statement = statement.where(
                    cast(Any, AuthAuditEventTable.created_at) >= since
                )
            if before is not None:
                before_created, before_id = before
                statement = statement.where(
                    sa.tuple_(
                        cast(Any, AuthAuditEventTable.created_at),
                        cast(Any, AuthAuditEventTable.id),
                    )
                    < sa.tuple_(sa.literal(before_created), sa.literal(before_id))
                )
            rows = session.exec(
                statement.order_by(
                    cast(Any, AuthAuditEventTable.created_at).desc(),
                    cast(Any, AuthAuditEventTable.id).desc(),
                ).limit(limit)
            ).all()
            return [_to_audit_event(row) for row in rows]
