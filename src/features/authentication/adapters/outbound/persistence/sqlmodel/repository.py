"""SQLModel-backed repository for the auth feature.

Owns every read and write against the auth schema. The class is intentionally
session-per-call rather than session-per-request so each repository method
defines its own transactional boundary and can be exercised in isolation
from the FastAPI request lifecycle (e.g. from the management CLI).

SQLModel table types are confined to this module. All public methods return
domain objects from ``src.features.authentication.domain.models`` so the application
layer remains free of persistence-framework types.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from types import TracebackType
from typing import Any, Self, cast, overload
from uuid import UUID

from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, create_engine, select

from src.features.authentication.adapters.outbound.persistence.sqlmodel.models import (
    AuthAuditEventTable,
    AuthInternalTokenTable,
    RefreshTokenTable,
    UserTable,
    utc_now,
)
from src.features.authentication.domain.models import (
    AuditEvent,
    InternalToken,
    RefreshToken,
    User,
)
from src.platform.shared.principal import Principal

# ── Mapper functions ─────────────────────────────────────────────────────────
# Each mapper converts a SQLModel table row into the corresponding domain type.
# SQLModel-specific types never leave this module.


@overload
def _ensure_utc(value: datetime) -> datetime: ...
@overload
def _ensure_utc(value: None) -> None: ...
def _ensure_utc(value: datetime | None) -> datetime | None:
    """Single boundary for tzinfo coercion.

    SQLite-backed test fixtures drop tzinfo on round-trip even though the
    column is declared ``DateTime(timezone=True)``. Coercing once here at
    the mapper boundary lets the domain validators reject naive datetimes
    everywhere else.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _to_user(row: UserTable) -> User:
    return User(
        id=row.id,
        email=row.email,
        password_hash=row.password_hash,
        is_active=row.is_active,
        is_verified=row.is_verified,
        authz_version=row.authz_version,
        created_at=_ensure_utc(row.created_at),
        updated_at=_ensure_utc(row.updated_at),
        last_login_at=_ensure_utc(row.last_login_at),
    )


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


def _get_principal_from_session(session: Session, user_id: UUID) -> Principal | None:
    """Build a ``Principal`` from the user row alone.

    Under ReBAC, the principal carries only identity and lifecycle flags;
    authorization is resolved through ``AuthorizationPort`` per check.
    """
    user = session.get(UserTable, user_id)
    if user is None:
        return None
    return Principal(
        user_id=user.id,
        email=user.email,
        is_active=user.is_active,
        is_verified=user.is_verified,
        authz_version=user.authz_version,
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

    def get_principal(self, user_id: UUID) -> Principal | None:
        return _get_principal_from_session(self._session, user_id)

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
        # A refresh-token family represents one continuous login chain for
        # a single user. If the family already has any token belonging to
        # a different user, refuse the write — silently letting one
        # family span users would corrupt theft-detection audit trails.
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

    def update_user_password(self, user_id: UUID, password_hash: str) -> None:
        user = self._session.get(UserTable, user_id)
        if user is None:
            return
        user.password_hash = password_hash
        user.authz_version += 1
        user.updated_at = utc_now()
        self._session.add(user)

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


class SQLModelAuthRepository:
    """SQLModel-backed persistence adapter for all auth and RBAC data.

    Provides a synchronous, session-scoped interface for users, roles,
    permissions, refresh tokens, internal tokens, and audit events.
    Most methods own one transaction; refresh-token rotation can borrow a
    single explicit transaction to lock, rotate, revoke, and audit atomically.
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
    ) -> None:
        """Create a repository connected to a PostgreSQL database.

        Args:
            database_url: A SQLAlchemy-compatible PostgreSQL DSN.
            create_schema: If ``True``, create all mapped tables before use.
                Intended for local development only; use Alembic in production.
            pool_size: Base connections held open per worker.
            max_overflow: Extra connections opened beyond ``pool_size`` under load.
            pool_recycle: Seconds before idle connections are recycled; defends
                against load-balancers that silently close idle TCP sessions.
            pool_pre_ping: When ``True``, every checked-out connection is
                pinged before use so a stale connection does not surface as
                a query-time error.

        Raises:
            ValueError: If ``database_url`` does not start with ``"postgresql"``.
        """
        if not database_url.startswith("postgresql"):
            # Auth models use PostgreSQL-specific types (UUID, JSONB) that
            # SQLite cannot handle, so an explicit guard surfaces this early.
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
        if create_schema:
            SQLModel.metadata.create_all(self._engine)

    @classmethod
    def from_engine(
        cls, engine: Engine, *, create_schema: bool = False
    ) -> "SQLModelAuthRepository":
        """Create a repository from an existing SQLAlchemy engine.

        Bypasses the PostgreSQL DSN guard, so any engine (including SQLite
        in-memory) can be injected — useful in tests.

        Args:
            engine: A pre-configured SQLAlchemy ``Engine`` instance.
            create_schema: If ``True``, create all mapped tables before use.

        Returns:
            A fully initialised ``SQLModelAuthRepository``.
        """
        # Bypass __init__ so tests can inject a pre-built engine (e.g. SQLite
        # in-memory) without triggering the PostgreSQL DSN guard.
        instance = cls.__new__(cls)
        instance._engine = engine
        instance._closed = False
        if create_schema:
            SQLModel.metadata.create_all(engine)
        return instance

    @property
    def engine(self) -> Engine:
        """Expose the underlying SQLAlchemy engine for tooling that needs raw access."""
        return self._engine

    def __enter__(self) -> Self:
        """Allow use as a context manager; the engine is disposed on exit."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Dispose the connection pool when leaving the ``with`` block."""
        del exc_type, exc, tb
        self.close()

    def close(self) -> None:
        """Dispose the connection pool and mark the repository as closed.

        Idempotent — safe to call more than once.
        """
        if self._closed:
            return
        self._engine.dispose()
        self._closed = True

    def _ensure_open(self) -> None:
        """Raise if the repository has already been closed.

        Raises:
            RuntimeError: If ``close()`` has been called.
        """
        if self._closed:
            raise RuntimeError("SQLModelAuthRepository is closed")

    @contextmanager
    def _session_scope(self) -> Iterator[Session]:
        """Open a read-only session that does not commit on exit.

        ``expire_on_commit=False`` keeps attributes accessible after the
        session closes, avoiding ``DetachedInstanceError`` when callers
        consume returned objects outside the ``with`` block.
        """
        self._ensure_open()
        with Session(self._engine, expire_on_commit=False) as session:
            yield session

    @contextmanager
    def _write_session_scope(self) -> Iterator[Session]:
        """Open a write session that commits on success and rolls back on any exception.

        Wrapping every mutation in this scope guarantees there is no
        partial state left in the database when an integrity error or
        unexpected failure interrupts a method midway through.
        """
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
        """Open one transaction for refresh-token rotation.

        The transaction object exposes ``get_refresh_token_for_update`` so the
        caller can lock the presented token row before validating and rotating it.
        """
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
        """Open one transaction for single-use internal-token consumption."""
        self._ensure_open()
        with Session(self._engine, expire_on_commit=False) as session:
            try:
                yield _SessionInternalTokenTransaction(session)
                session.commit()
            except Exception:
                session.rollback()
                raise

    def get_user_by_email(self, email: str) -> User | None:
        with self._session_scope() as session:
            row = session.exec(
                select(UserTable).where(UserTable.email == email)
            ).one_or_none()
            return _to_user(row) if row is not None else None

    def get_user_by_id(self, user_id: UUID) -> User | None:
        with self._session_scope() as session:
            row = session.get(UserTable, user_id)
            return _to_user(row) if row is not None else None

    def list_users(self, *, limit: int = 100, offset: int = 0) -> list[User]:
        with self._session_scope() as session:
            rows = list(
                session.exec(
                    select(UserTable)
                    .order_by(UserTable.email)
                    .offset(offset)
                    .limit(limit)
                ).all()
            )
            return [_to_user(r) for r in rows]

    def create_user(self, *, email: str, password_hash: str) -> User | None:
        user = UserTable(email=email, password_hash=password_hash)
        try:
            with self._write_session_scope() as session:
                session.add(user)
                session.flush()
                session.refresh(user)
                return _to_user(user)
        except IntegrityError:
            return None

    def update_user_login(self, user_id: UUID, when: datetime) -> None:
        with self._write_session_scope() as session:
            user = session.get(UserTable, user_id)
            if user is None:
                return
            user.last_login_at = when
            user.updated_at = when
            session.add(user)

    def set_user_active(self, user_id: UUID, is_active: bool) -> None:
        with self._write_session_scope() as session:
            user = session.get(UserTable, user_id)
            if user is None:
                return
            user.is_active = is_active
            # Bumping authz_version alongside the status change ensures any
            # existing access tokens are rejected on the very next request,
            # not just after they expire.
            user.authz_version += 1
            user.updated_at = utc_now()
            session.add(user)

    def set_user_verified(self, user_id: UUID) -> None:
        with self._write_session_scope() as session:
            user = session.get(UserTable, user_id)
            if user is None:
                return
            user.is_verified = True
            user.updated_at = utc_now()
            session.add(user)

    def update_user_password(self, user_id: UUID, password_hash: str) -> None:
        with self._write_session_scope() as session:
            user = session.get(UserTable, user_id)
            if user is None:
                return
            user.password_hash = password_hash
            # Incrementing authz_version on password change invalidates all
            # active access tokens, closing the window where a compromised
            # token remains valid after a forced password reset.
            user.authz_version += 1
            user.updated_at = utc_now()
            session.add(user)

    def increment_user_authz_version(self, user_id: UUID) -> None:
        with self._write_session_scope() as session:
            user = session.get(UserTable, user_id)
            if user is None:
                return
            user.authz_version += 1
            user.updated_at = utc_now()
            session.add(user)

    def get_principal(self, user_id: UUID) -> Principal | None:
        """Build a ``Principal`` from a user's current DB state.

        Called on every authenticated request. Authorization is no longer
        carried on the principal; callers consult ``AuthorizationPort``
        for resource-scoped checks.
        """
        with self._session_scope() as session:
            return _get_principal_from_session(session, user_id)

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
            # Preserve the original revocation timestamp if already set so
            # that concurrent revocations do not overwrite the forensic record.
            token.revoked_at = token.revoked_at or utc_now()
            token.replaced_by_token_id = replaced_by_token_id
            session.add(token)

    def revoke_refresh_family(self, family_id: UUID) -> None:
        """Revoke all refresh tokens that belong to the same login chain."""
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
        """Revoke all active refresh tokens for a user (logout-all / password reset)."""
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
        """Record that a single-use internal token has been consumed.

        Idempotent: if already marked, the original timestamp is preserved.
        """
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

    def list_audit_events(
        self,
        *,
        user_id: UUID | None = None,
        event_type: str | None = None,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[AuditEvent]:
        """Return audit events ordered by newest first with optional filters."""
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
            rows = session.exec(
                statement.order_by(
                    cast(Any, AuthAuditEventTable.created_at).desc()
                ).limit(limit)
            ).all()
            return [_to_audit_event(row) for row in rows]
