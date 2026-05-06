"""SQLModel-backed repository for the auth feature.

Owns every read and write against the auth schema. The class is intentionally
session-per-call rather than session-per-request so each repository method
defines its own transactional boundary and can be exercised in isolation
from the FastAPI request lifecycle (e.g. from the management CLI).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from types import TracebackType
from typing import Any, Self, cast
from uuid import UUID

from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, create_engine, select

from src.features.auth.adapters.outbound.persistence.sqlmodel.models import (
    AuthAuditEventTable,
    AuthInternalTokenTable,
    PermissionTable,
    RefreshTokenTable,
    RolePermissionTable,
    RoleTable,
    UserRoleTable,
    UserTable,
    utc_now,
)
from src.features.auth.application.types import Principal


class SQLModelAuthRepository:
    """SQLModel-backed persistence adapter for all auth and RBAC data.

    Provides a synchronous, session-scoped interface for users, roles,
    permissions, refresh tokens, internal tokens, and audit events.
    All writes are wrapped in transactions that roll back on failure.
    """

    def __init__(self, database_url: str, *, create_schema: bool = False) -> None:
        """Create a repository connected to a PostgreSQL database.

        Args:
            database_url: A SQLAlchemy-compatible PostgreSQL DSN.
            create_schema: If ``True``, create all mapped tables before use.
                Intended for local development only; use Alembic in production.

        Raises:
            ValueError: If ``database_url`` does not start with ``"postgresql"``.
        """
        if not database_url.startswith("postgresql"):
            # Auth models use PostgreSQL-specific types (UUID, JSONB) that
            # SQLite cannot handle, so an explicit guard surfaces this early.
            msg = "SQLModelAuthRepository supports PostgreSQL DSNs only"
            raise ValueError(msg)
        # pool_pre_ping recycles stale connections after a DB restart or
        # network interruption without raising errors to callers.
        self._engine = create_engine(database_url, pool_pre_ping=True)
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

    def get_user_by_email(self, email: str) -> UserTable | None:
        """Look up a user by their normalised email address.

        Args:
            email: The canonical (lowercased) email to search for.

        Returns:
            The matching ``UserTable`` row, or ``None`` if not found.
        """
        with self._session_scope() as session:
            return session.exec(
                select(UserTable).where(UserTable.email == email)
            ).one_or_none()

    def get_user_by_id(self, user_id: UUID) -> UserTable | None:
        """Look up a user by primary key.

        Args:
            user_id: The user's UUID.

        Returns:
            The matching ``UserTable`` row, or ``None`` if not found.
        """
        with self._session_scope() as session:
            return session.get(UserTable, user_id)

    def list_users(self) -> list[UserTable]:
        """Return all users ordered alphabetically by email.

        Returns:
            A list of ``UserTable`` rows (may be empty).
        """
        with self._session_scope() as session:
            return list(session.exec(select(UserTable).order_by(UserTable.email)).all())

    def create_user(self, *, email: str, password_hash: str) -> UserTable | None:
        """Persist a new user record.

        Args:
            email: The normalised email address (must be unique).
            password_hash: The Argon2id hash of the user's password.

        Returns:
            The newly created ``UserTable`` row, or ``None`` if the email
            is already registered (integrity constraint violation).
        """
        user = UserTable(email=email, password_hash=password_hash)
        try:
            with self._write_session_scope() as session:
                session.add(user)
                session.flush()
                session.refresh(user)
                return user
        except IntegrityError:
            return None

    def update_user_login(self, user_id: UUID, when: datetime) -> None:
        """Record the timestamp of a successful login.

        Args:
            user_id: The user's UUID.
            when: The UTC datetime of the login event.
        """
        with self._write_session_scope() as session:
            user = session.get(UserTable, user_id)
            if user is None:
                return
            user.last_login_at = when
            user.updated_at = when
            session.add(user)

    def set_user_active(self, user_id: UUID, is_active: bool) -> None:
        """Activate or deactivate a user account and bump their authz_version.

        Args:
            user_id: The user's UUID.
            is_active: ``True`` to enable the account, ``False`` to disable it.
        """
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
        """Mark a user's email address as verified.

        Args:
            user_id: The user's UUID.
        """
        with self._write_session_scope() as session:
            user = session.get(UserTable, user_id)
            if user is None:
                return
            user.is_verified = True
            user.updated_at = utc_now()
            session.add(user)

    def update_user_password(self, user_id: UUID, password_hash: str) -> None:
        """Replace a user's password hash and bump their authz_version.

        Args:
            user_id: The user's UUID.
            password_hash: The new Argon2id hash to store.
        """
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
        """Bump a single user's authz_version to invalidate their active tokens.

        Args:
            user_id: The user's UUID.
        """
        with self._write_session_scope() as session:
            user = session.get(UserTable, user_id)
            if user is None:
                return
            user.authz_version += 1
            user.updated_at = utc_now()
            session.add(user)

    def increment_authz_for_role_users(self, role_id: UUID) -> None:
        """Bump authz_version for every user that holds the given role.

        Called after any role or permission change so that all affected users'
        active tokens become stale on their next request.

        Args:
            role_id: The role whose members should have their version bumped.
        """
        with self._write_session_scope() as session:
            links = session.exec(
                select(UserRoleTable).where(UserRoleTable.role_id == role_id)
            ).all()
            for link in links:
                user = session.get(UserTable, link.user_id)
                if user is not None:
                    user.authz_version += 1
                    user.updated_at = utc_now()
                    session.add(user)

    def get_principal(self, user_id: UUID) -> Principal | None:
        """Build a ``Principal`` from a user's current DB state.

        Resolves the user's active roles and their associated permissions
        in a single session. Called on every authenticated request.

        Args:
            user_id: The user's UUID.

        Returns:
            A fully populated ``Principal``, or ``None`` if the user does not exist.
        """
        with self._session_scope() as session:
            user = session.get(UserTable, user_id)
            if user is None:
                return None
            # Only roles with is_active=True contribute permissions so that
            # deactivating a role immediately removes its grants for everyone
            # who holds it, without touching individual user assignments.
            roles = session.exec(
                select(RoleTable.name)
                .join(
                    UserRoleTable,
                    cast(Any, UserRoleTable.role_id == RoleTable.id),
                )
                .where(
                    cast(Any, UserRoleTable.user_id == user_id),
                    cast(Any, RoleTable.is_active).is_(True),
                )
                .distinct()
            ).all()
            permissions = session.exec(
                select(PermissionTable.name)
                .join(
                    RolePermissionTable,
                    cast(
                        Any,
                        RolePermissionTable.permission_id == PermissionTable.id,
                    ),
                )
                .join(
                    RoleTable,
                    cast(Any, RoleTable.id == RolePermissionTable.role_id),
                )
                .join(
                    UserRoleTable,
                    cast(Any, UserRoleTable.role_id == RoleTable.id),
                )
                .where(
                    cast(Any, UserRoleTable.user_id == user_id),
                    cast(Any, RoleTable.is_active).is_(True),
                )
                .distinct()
            ).all()
            return Principal(
                user_id=user.id,
                email=user.email,
                is_active=user.is_active,
                is_verified=user.is_verified,
                authz_version=user.authz_version,
                roles=frozenset(str(role) for role in roles),
                permissions=frozenset(str(permission) for permission in permissions),
            )

    def list_roles(self) -> list[RoleTable]:
        """Return all roles ordered alphabetically by name.

        Returns:
            A list of ``RoleTable`` rows (may be empty).
        """
        with self._session_scope() as session:
            return list(session.exec(select(RoleTable).order_by(RoleTable.name)).all())

    def get_role(self, role_id: UUID) -> RoleTable | None:
        """Look up a role by primary key.

        Args:
            role_id: The role's UUID.

        Returns:
            The matching ``RoleTable`` row, or ``None`` if not found.
        """
        with self._session_scope() as session:
            return session.get(RoleTable, role_id)

    def get_role_by_name(self, name: str) -> RoleTable | None:
        """Look up a role by its normalised name.

        Args:
            name: The canonical role name (e.g. ``"super_admin"``).

        Returns:
            The matching ``RoleTable`` row, or ``None`` if not found.
        """
        with self._session_scope() as session:
            return session.exec(
                select(RoleTable).where(RoleTable.name == name)
            ).one_or_none()

    def create_role(
        self, *, name: str, description: str | None = None
    ) -> RoleTable | None:
        """Persist a new role.

        Args:
            name: The normalised role name (must be unique).
            description: Optional human-readable description.

        Returns:
            The created ``RoleTable`` row, or ``None`` if the name already exists.
        """
        role = RoleTable(name=name, description=description)
        try:
            with self._write_session_scope() as session:
                session.add(role)
                session.flush()
                session.refresh(role)
                return role
        except IntegrityError:
            return None

    def update_role(
        self,
        role_id: UUID,
        *,
        name: str | None = None,
        description: str | None = None,
        is_active: bool | None = None,
    ) -> RoleTable | None:
        """Update mutable fields of an existing role.

        Only fields provided (non-``None``) are changed.

        Args:
            role_id: The role's UUID.
            name: New normalised name, or ``None`` to leave unchanged.
            description: New description, or ``None`` to leave unchanged.
            is_active: New active status, or ``None`` to leave unchanged.

        Returns:
            The updated ``RoleTable`` row, or ``None`` if the role was not found
            or a name conflict occurred.
        """
        try:
            with self._write_session_scope() as session:
                role = session.get(RoleTable, role_id)
                if role is None:
                    return None
                if name is not None:
                    role.name = name
                if description is not None:
                    role.description = description
                if is_active is not None:
                    role.is_active = is_active
                role.updated_at = utc_now()
                session.add(role)
                session.flush()
                session.refresh(role)
                return role
        except IntegrityError:
            return None

    def list_permissions(self) -> list[PermissionTable]:
        """Return all permissions ordered alphabetically by name.

        Returns:
            A list of ``PermissionTable`` rows (may be empty).
        """
        with self._session_scope() as session:
            return list(
                session.exec(
                    select(PermissionTable).order_by(PermissionTable.name)
                ).all()
            )

    def get_permission(self, permission_id: UUID) -> PermissionTable | None:
        """Look up a permission by primary key.

        Args:
            permission_id: The permission's UUID.

        Returns:
            The matching ``PermissionTable`` row, or ``None`` if not found.
        """
        with self._session_scope() as session:
            return session.get(PermissionTable, permission_id)

    def get_permission_by_name(self, name: str) -> PermissionTable | None:
        """Look up a permission by its normalised name.

        Args:
            name: The canonical permission name (e.g. ``"roles:read"``).

        Returns:
            The matching ``PermissionTable`` row, or ``None`` if not found.
        """
        with self._session_scope() as session:
            return session.exec(
                select(PermissionTable).where(PermissionTable.name == name)
            ).one_or_none()

    def create_permission(
        self, *, name: str, description: str | None = None
    ) -> PermissionTable | None:
        """Persist a new permission.

        Args:
            name: The normalised permission name (must be unique).
            description: Optional human-readable description.

        Returns:
            The created ``PermissionTable`` row, or ``None`` if the name already exists.
        """
        permission = PermissionTable(name=name, description=description)
        try:
            with self._write_session_scope() as session:
                session.add(permission)
                session.flush()
                session.refresh(permission)
                return permission
        except IntegrityError:
            return None

    def assign_user_role(self, user_id: UUID, role_id: UUID) -> bool:
        """Grant a role to a user and bump their authz_version.

        Idempotent: if the assignment already exists, the version is not bumped again.

        Args:
            user_id: The user's UUID.
            role_id: The role's UUID.

        Returns:
            ``True`` on success, ``False`` if the user or role does not exist.
        """
        with self._write_session_scope() as session:
            if (
                session.get(UserTable, user_id) is None
                or session.get(RoleTable, role_id) is None
            ):
                return False
            existing = session.get(UserRoleTable, (user_id, role_id))
            if existing is None:
                session.add(UserRoleTable(user_id=user_id, role_id=role_id))
                user = session.get(UserTable, user_id)
                if user is not None:
                    user.authz_version += 1
                    user.updated_at = utc_now()
                    session.add(user)
            return True

    def remove_user_role(self, user_id: UUID, role_id: UUID) -> bool:
        """Revoke a role from a user and bump their authz_version.

        Args:
            user_id: The user's UUID.
            role_id: The role's UUID.

        Returns:
            ``True`` if the assignment was removed, ``False`` if it did not exist.
        """
        with self._write_session_scope() as session:
            link = session.get(UserRoleTable, (user_id, role_id))
            if link is None:
                return False
            session.delete(link)
            user = session.get(UserTable, user_id)
            if user is not None:
                user.authz_version += 1
                user.updated_at = utc_now()
                session.add(user)
            return True

    def assign_role_permission(self, role_id: UUID, permission_id: UUID) -> bool:
        """Grant a permission to a role.

        Idempotent: if the assignment already exists, no duplicate is created.

        Args:
            role_id: The role's UUID.
            permission_id: The permission's UUID.

        Returns:
            ``True`` on success, ``False`` if the role or permission does not exist.
        """
        with self._write_session_scope() as session:
            if (
                session.get(RoleTable, role_id) is None
                or session.get(PermissionTable, permission_id) is None
            ):
                return False
            existing = session.get(RolePermissionTable, (role_id, permission_id))
            if existing is None:
                session.add(
                    RolePermissionTable(role_id=role_id, permission_id=permission_id)
                )
            return True

    def remove_role_permission(self, role_id: UUID, permission_id: UUID) -> bool:
        """Revoke a permission from a role.

        Args:
            role_id: The role's UUID.
            permission_id: The permission's UUID.

        Returns:
            ``True`` if the assignment was removed, ``False`` if it did not exist.
        """
        with self._write_session_scope() as session:
            link = session.get(RolePermissionTable, (role_id, permission_id))
            if link is None:
                return False
            session.delete(link)
            return True

    def create_refresh_token(
        self,
        *,
        user_id: UUID,
        token_hash: str,
        family_id: UUID,
        expires_at: datetime,
        created_ip: str | None,
        user_agent: str | None,
    ) -> RefreshTokenTable:
        """Persist a new refresh token record.

        Args:
            user_id: The owner's UUID.
            token_hash: SHA-256 hex digest of the opaque token (never the token itself).
            family_id: UUID grouping this token with others from the same login chain.
            expires_at: UTC datetime after which the token is no longer valid.
            created_ip: Client IP address at the time of issuance, or ``None``.
            user_agent: Client User-Agent header at the time of issuance, or ``None``.

        Returns:
            The persisted ``RefreshTokenTable`` row.
        """
        refresh = RefreshTokenTable(
            user_id=user_id,
            token_hash=token_hash,
            family_id=family_id,
            expires_at=expires_at,
            created_ip=created_ip,
            user_agent=user_agent,
        )
        with self._write_session_scope() as session:
            session.add(refresh)
            session.flush()
            session.refresh(refresh)
            return refresh

    def get_refresh_token_by_hash(self, token_hash: str) -> RefreshTokenTable | None:
        """Find a refresh token record by its stored hash.

        Args:
            token_hash: SHA-256 hex digest of the opaque token.

        Returns:
            The matching ``RefreshTokenTable`` row, or ``None`` if not found.
        """
        with self._session_scope() as session:
            return session.exec(
                select(RefreshTokenTable).where(
                    RefreshTokenTable.token_hash == token_hash
                )
            ).one_or_none()

    def revoke_refresh_token(
        self, token_id: UUID, *, replaced_by_token_id: UUID | None = None
    ) -> None:
        """Mark a single refresh token as revoked.

        Args:
            token_id: The refresh token's UUID.
            replaced_by_token_id: UUID of the token that replaced this one
                during rotation, or ``None`` for a plain revocation.
        """
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
        """Revoke all refresh tokens that belong to the same login chain.

        Called when token reuse is detected to prevent an attacker from
        keeping a stolen token alive after it has been rotated.

        Args:
            family_id: The UUID shared by all tokens in the chain.
        """
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
        """Revoke all active refresh tokens for a user (logout-all / password reset).

        Args:
            user_id: The user whose sessions should all be terminated.
        """
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
    ) -> AuthInternalTokenTable:
        """Persist a single-use internal token (password reset or email verification).

        Args:
            user_id: The owner's UUID, or ``None`` for anonymous flows.
            purpose: One of ``"password_reset"`` or ``"email_verify"``.
            token_hash: SHA-256 hex digest of the opaque token.
            expires_at: UTC datetime after which the token must be rejected.
            created_ip: Client IP address at the time of issuance, or ``None``.

        Returns:
            The persisted ``AuthInternalTokenTable`` row.
        """
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
            return token

    def get_internal_token(
        self, *, token_hash: str, purpose: str
    ) -> AuthInternalTokenTable | None:
        """Find an internal token by its hash and purpose.

        Args:
            token_hash: SHA-256 hex digest of the opaque token.
            purpose: Expected purpose; mismatched purpose returns ``None``.

        Returns:
            The matching ``AuthInternalTokenTable`` row, or ``None`` if not found.
        """
        with self._session_scope() as session:
            return session.exec(
                select(AuthInternalTokenTable).where(
                    AuthInternalTokenTable.token_hash == token_hash,
                    AuthInternalTokenTable.purpose == purpose,
                )
            ).one_or_none()

    def mark_internal_token_used(self, token_id: UUID) -> None:
        """Record that a single-use internal token has been consumed.

        Idempotent: if already marked, the original timestamp is preserved.

        Args:
            token_id: The internal token's UUID.
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
        """Append an immutable audit event to the log.

        Args:
            event_type: Dot-namespaced id (e.g. ``"auth.login_succeeded"``).
            user_id: Acting or affected user UUID, or ``None`` if anonymous.
            ip_address: Client IP address, or ``None`` if not available.
            user_agent: Client User-Agent header, or ``None`` if not available.
            metadata: Arbitrary JSON-serialisable context dictionary.
        """
        event = AuthAuditEventTable(
            user_id=user_id,
            event_type=event_type,
            ip_address=ip_address,
            user_agent=user_agent,
            event_metadata=metadata or {},
        )
        with self._write_session_scope() as session:
            session.add(event)

    def list_audit_events(self) -> list[AuthAuditEventTable]:
        """Return all audit events ordered chronologically.

        Returns:
            A list of ``AuthAuditEventTable`` rows sorted by ``created_at`` ascending.
        """
        with self._session_scope() as session:
            return list(
                session.exec(
                    select(AuthAuditEventTable).order_by(
                        cast(Any, AuthAuditEventTable.created_at)
                    )
                ).all()
            )
