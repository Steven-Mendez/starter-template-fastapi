"""High-level auth and RBAC use cases.

This module hosts :class:`AuthService` (registration, login, token rotation,
password reset, email verification) and :class:`RBACService` (roles,
permissions, and assignments). Every flow records audit events and bumps
``authz_version`` whenever a change must invalidate already-issued tokens
without waiting for their JWT expiry.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

from src.features.auth.application.cache import (
    InProcessPrincipalCache,
    PrincipalCachePort,
)
from src.features.auth.application.crypto import (
    PasswordService,
    generate_opaque_token,
    hash_token,
)
from src.features.auth.application.errors import (
    ConflictError,
    DuplicateEmailError,
    EmailNotVerifiedError,
    InactiveUserError,
    InvalidCredentialsError,
    InvalidTokenError,
    NotFoundError,
    PermissionDeniedError,
    StaleTokenError,
    TokenAlreadyUsedError,
)
from src.features.auth.application.jwt_tokens import AccessTokenService
from src.features.auth.application.normalization import (
    is_permission_name,
    is_role_name,
    normalize_email,
    normalize_permission_name,
    normalize_role_name,
)
from src.features.auth.application.ports.outbound.auth_repository import (
    AuthRepositoryPort,
)
from src.features.auth.application.seed import (
    ALL_PERMISSIONS,
    ROLE_DESCRIPTIONS,
    ROLE_PERMISSIONS,
)
from src.features.auth.application.types import (
    InternalTokenResult,
    IssuedTokens,
    Principal,
)
from src.features.auth.domain.models import (
    AuditEvent,
    InternalToken,
    Permission,
    RefreshToken,
    Role,
    User,
)
from src.platform.config.settings import AppSettings

# Purpose strings are validated by a DB CHECK constraint, so typos fail at
# the database level rather than silently creating unreachable tokens.
PASSWORD_RESET_PURPOSE = "password_reset"
EMAIL_VERIFY_PURPOSE = "email_verify"

_logger = logging.getLogger(__name__)


class AuthService:
    """Orchestrates all user-facing authentication flows.

    Handles registration, login, token rotation, logout, password reset,
    and email verification. All operations are audited and any domain error
    is surfaced as a subclass of ``AuthError`` for the HTTP layer to map.
    """

    def __init__(
        self,
        *,
        repository: AuthRepositoryPort,
        settings: AppSettings,
        password_service: PasswordService,
        token_service: AccessTokenService,
        cache: PrincipalCachePort | None = None,
    ) -> None:
        self._repo = repository
        self._settings = settings
        self._passwords = password_service
        self._tokens = token_service
        self._cache: PrincipalCachePort = cache or InProcessPrincipalCache.create(
            ttl=settings.auth_principal_cache_ttl_seconds
        )
        # Pre-compute a dummy hash at startup so that login attempts for
        # non-existent emails spend the same time verifying a hash as for
        # real users, preventing user-enumeration via timing differences.
        self._dummy_hash = self._passwords.hash_password("dummy-password")

    def register(
        self,
        *,
        email: str,
        password: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> User:
        """Create a new user account and assign the default role.

        The default role (``auth_default_user_role``) is only assigned if it
        exists and is not ``super_admin``, preventing accidental privilege
        escalation through the public registration endpoint.

        Args:
            email: Raw email address; normalised before persistence.
            password: Plaintext password; hashed with Argon2id before storage.
            ip_address: Client IP for audit logging.
            user_agent: Client User-Agent for audit logging.

        Returns:
            The newly created ``UserTable`` row with roles loaded.

        Raises:
            DuplicateEmailError: If the email is already registered.
        """
        normalized_email = normalize_email(email)
        password_hash = self._passwords.hash_password(password)
        user = self._repo.create_user(
            email=normalized_email, password_hash=password_hash
        )
        if user is None:
            raise DuplicateEmailError("Email already registered")
        default_role = self._repo.get_role_by_name(
            normalize_role_name(self._settings.auth_default_user_role)
        )
        if (
            default_role is not None
            and default_role.name != self._settings.auth_super_admin_role
        ):
            self._repo.assign_user_role(user.id, default_role.id)
        self._repo.record_audit_event(
            event_type="auth.user_registered",
            user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        fresh = self._repo.get_user_by_id(user.id)
        if fresh is None:
            raise NotFoundError("User not found after registration")
        return fresh

    def login(
        self,
        *,
        email: str,
        password: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[IssuedTokens, Principal]:
        """Authenticate a user and issue a token pair.

        Runs the Argon2 verification even for unknown emails so the response
        time does not reveal whether an account exists. Deactivated users are
        rejected with the same generic error as a wrong password, avoiding
        account-status enumeration.

        Args:
            email: Raw email; normalised before lookup.
            password: Plaintext password to verify against the stored hash.
            ip_address: Client IP for audit logging and rate-limit keying.
            user_agent: Client User-Agent for audit logging.

        Returns:
            A tuple of ``(IssuedTokens, Principal)`` for the authenticated user.

        Raises:
            InvalidCredentialsError: If the email is not found, the password
                does not match, or the account is inactive.
        """
        normalized_email = normalize_email(email)
        user = self._repo.get_user_by_email(normalized_email)
        if user is None:
            # Run a real hash verification against the dummy hash so the
            # response time is indistinguishable from a failed password match,
            # preventing user-enumeration through response latency.
            self._passwords.verify_password(self._dummy_hash, password)
            self._repo.record_audit_event(
                event_type="auth.login_failed",
                ip_address=ip_address,
                user_agent=user_agent,
                metadata={"reason": "invalid_credentials"},
            )
            raise InvalidCredentialsError("Invalid credentials")
        if not self._passwords.verify_password(user.password_hash, password):
            self._repo.record_audit_event(
                event_type="auth.login_failed",
                user_id=user.id,
                ip_address=ip_address,
                user_agent=user_agent,
                metadata={"reason": "invalid_credentials"},
            )
            raise InvalidCredentialsError("Invalid credentials")
        if not user.is_active:
            self._repo.record_audit_event(
                event_type="auth.login_failed",
                user_id=user.id,
                ip_address=ip_address,
                user_agent=user_agent,
                metadata={"reason": "inactive_user"},
            )
            raise InactiveUserError("Inactive user")
        if self._settings.auth_require_email_verification and not user.is_verified:
            self._repo.record_audit_event(
                event_type="auth.login_failed",
                user_id=user.id,
                ip_address=ip_address,
                user_agent=user_agent,
                metadata={"reason": "email_not_verified"},
            )
            raise EmailNotVerifiedError("Email not verified")
        self._repo.update_user_login(user.id, datetime.now(timezone.utc))
        tokens, principal = self._issue_tokens(
            user.id, ip_address=ip_address, user_agent=user_agent
        )
        self._repo.record_audit_event(
            event_type="auth.login_succeeded",
            user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return tokens, principal

    def principal_from_access_token(self, token: str) -> Principal:
        """Validate a JWT and resolve the current identity from the database.

        Results are cached for up to 30 seconds keyed by the token's ``jti``
        claim to avoid a DB round-trip on every authenticated request. Permission
        or role revocations can therefore take up to 30 seconds to propagate for
        tokens whose principal is already cached.

        Args:
            token: Encoded JWT access token received from the client.

        Returns:
            The verified and active ``Principal`` for the token's subject.

        Raises:
            InvalidTokenError: If the JWT is malformed, expired, or the user
                no longer exists.
            InactiveUserError: If the account has been deactivated.
            StaleTokenError: If the token's ``authz_version`` does not match
                the current DB value (permission set has changed).
        """
        payload = self._tokens.decode(token)
        token_id = payload.token_id

        cached = self._cache.get(token_id)
        if cached is not None:
            return cached

        principal = self._repo.get_principal(payload.subject)
        if principal is None:
            raise InvalidTokenError("Could not validate credentials")
        if not principal.is_active:
            raise InactiveUserError("Inactive user")
        if principal.authz_version != payload.authz_version:
            # Evict any stale entry and reject the request so the client must
            # re-authenticate with a freshly issued token.
            self._cache.pop(token_id)
            raise StaleTokenError("Stale authorization token")

        self._cache.set(token_id, principal)
        return principal

    def invalidate_principal_cache_for_user(self, user_id: UUID) -> None:
        """Evict all cached principals for ``user_id``.

        Called by ``logout_all`` so that sessions are denied immediately
        rather than waiting for the 30-second TTL to elapse.
        """
        self._cache.invalidate_user(user_id)

    def refresh(
        self,
        *,
        refresh_token: str | None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[IssuedTokens, Principal]:
        """Rotate a refresh token and issue a new token pair.

        If the presented token has already been used (revoked), the entire
        token family is revoked to limit the damage from a stolen token. The
        old token is always revoked and linked to its replacement to maintain
        a full audit chain.

        Args:
            refresh_token: The opaque refresh token from the cookie.
            ip_address: Client IP for audit logging.
            user_agent: Client User-Agent for audit logging.

        Returns:
            A new ``(IssuedTokens, Principal)`` pair.

        Raises:
            InvalidTokenError: If the token is missing, not found, already
                revoked, or expired.
        """
        if not refresh_token:
            raise InvalidTokenError("Invalid refresh token")

        invalid_token_error: InvalidTokenError | None = None
        tokens: IssuedTokens | None = None
        principal: Principal | None = None
        with self._repo.refresh_token_transaction() as tx:
            record = tx.get_refresh_token_for_update(hash_token(refresh_token))
            if record is None:
                raise InvalidTokenError("Invalid refresh token")

            now = datetime.now(timezone.utc)
            if record.revoked_at is not None:
                # A revoked token being presented again signals a theft scenario:
                # the original token was likely stolen and used after rotation.
                # Revoking the entire family forces all active sessions for that
                # login chain to re-authenticate.
                tx.revoke_refresh_family(record.family_id)
                tx.record_audit_event(
                    event_type="auth.refresh_reuse_detected",
                    user_id=record.user_id,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    metadata={"family_id": str(record.family_id)},
                )
                invalid_token_error = InvalidTokenError("Invalid refresh token")
            elif record.expires_at <= now:
                tx.revoke_refresh_token(record.id)
                invalid_token_error = InvalidTokenError("Invalid refresh token")
            else:
                principal = tx.get_principal(record.user_id)
                if principal is None:
                    raise InvalidCredentialsError("Invalid credentials")
                if not principal.is_active:
                    raise InactiveUserError("Inactive user")

                access_token, expires_in = self._tokens.issue(
                    subject=record.user_id,
                    roles=set(principal.roles),
                    authz_version=principal.authz_version,
                )
                raw_refresh_token = generate_opaque_token()
                replacement = tx.create_refresh_token(
                    user_id=record.user_id,
                    token_hash=hash_token(raw_refresh_token),
                    family_id=record.family_id,
                    expires_at=now
                    + timedelta(days=self._settings.auth_refresh_token_expire_days),
                    created_ip=ip_address,
                    user_agent=user_agent,
                )
                tx.revoke_refresh_token(
                    record.id,
                    replaced_by_token_id=replacement.id,
                )
                tx.record_audit_event(
                    event_type="auth.refresh_succeeded",
                    user_id=record.user_id,
                    ip_address=ip_address,
                    user_agent=user_agent,
                )
                tokens = IssuedTokens(
                    access_token=access_token,
                    refresh_token=raw_refresh_token,
                    token_type="bearer",
                    expires_in=expires_in,
                )

        if invalid_token_error is not None:
            raise invalid_token_error
        if tokens is None or principal is None:
            raise InvalidTokenError("Invalid refresh token")
        return tokens, principal

    def logout(self, refresh_token: str | None) -> None:
        """Revoke the current session's refresh token.

        Silent no-op if no token is provided or the token is already revoked,
        so clients can call this endpoint safely without a valid session.

        Args:
            refresh_token: The opaque refresh token from the cookie.
        """
        if not refresh_token:
            return
        record = self._repo.get_refresh_token_by_hash(hash_token(refresh_token))
        if record is not None and record.revoked_at is None:
            self._repo.revoke_refresh_token(record.id)

    def logout_all(
        self,
        *,
        user_id: UUID,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """Revoke all active sessions for a user simultaneously.

        Useful when a user suspects their account has been compromised or
        when an admin wants to force re-authentication on all devices.

        Args:
            user_id: The user whose sessions should all be terminated.
            ip_address: Client IP for audit logging.
            user_agent: Client User-Agent for audit logging.
        """
        self._repo.revoke_user_refresh_tokens(user_id)
        self.invalidate_principal_cache_for_user(user_id)
        self._repo.record_audit_event(
            event_type="auth.logout_all",
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    def request_password_reset(
        self,
        *,
        email: str,
        ip_address: str | None = None,
    ) -> InternalTokenResult:
        """Create a password-reset token for the given email, if the account exists.

        Always returns a result with the same shape regardless of whether the
        account exists, so the HTTP layer can respond identically in both cases
        and prevent user enumeration through this endpoint.

        The ``token`` field in the result is only populated when
        ``AUTH_RETURN_INTERNAL_TOKENS=true`` (local development / tests).
        In production it is ``None`` and the token is delivered via email.

        Args:
            email: Raw email; normalised before lookup.
            ip_address: Client IP for audit logging.

        Returns:
            An ``InternalTokenResult`` with ``token=None`` when the account
            does not exist or when the setting is disabled.
        """
        user = self._repo.get_user_by_email(normalize_email(email))
        if user is None:
            return InternalTokenResult(token=None, expires_at=None)
        token, expires_at = self._create_internal_token(
            user_id=user.id,
            purpose=PASSWORD_RESET_PURPOSE,
            expires_delta=timedelta(
                minutes=self._settings.auth_password_reset_token_expire_minutes
            ),
            ip_address=ip_address,
        )
        self._repo.record_audit_event(
            event_type="auth.password_reset_requested",
            user_id=user.id,
            ip_address=ip_address,
        )
        # Whether the dev_token is returned is a deployment-wide config; logging
        # it here would spam logs once per request. The startup-time check in
        # ``build_auth_container`` reports the missing delivery provider once.
        return InternalTokenResult(
            token=token if self._settings.auth_return_internal_tokens else None,
            expires_at=expires_at,
        )

    def reset_password(self, *, token: str, new_password: str) -> None:
        """Apply a new password and invalidate all existing sessions.

        Revoking all sessions ensures an attacker who triggered the reset
        cannot continue using a previously stolen session after the password
        is changed.

        Args:
            token: The single-use opaque reset token from the email link.
            new_password: The plaintext replacement password to hash and store.

        Raises:
            InvalidTokenError: If the token is unknown, already used, or expired.
        """
        user_id: UUID | None = None
        with self._repo.internal_token_transaction() as tx:
            record = tx.get_internal_token_for_update(
                token_hash=hash_token(token), purpose=PASSWORD_RESET_PURPOSE
            )
            if record is None or record.expires_at <= datetime.now(timezone.utc):
                raise InvalidTokenError("Invalid token")
            if record.used_at is not None:
                raise TokenAlreadyUsedError("Token already used")
            if record.user_id is None:
                raise InvalidTokenError("Invalid token")
            user_id = record.user_id
            tx.update_user_password(
                user_id, self._passwords.hash_password(new_password)
            )
            tx.mark_internal_token_used(record.id)
            # Revoke all sessions after a password reset so that an attacker who
            # triggered the reset cannot keep using a previously stolen session.
            tx.revoke_user_refresh_tokens(user_id)
            tx.record_audit_event(
                event_type="auth.password_reset_completed",
                user_id=user_id,
            )
        if user_id is not None:
            self.invalidate_principal_cache_for_user(user_id)

    def request_email_verification(
        self,
        *,
        user_id: UUID,
        ip_address: str | None = None,
    ) -> InternalTokenResult:
        """Create an email-verification token for an authenticated user.

        Args:
            user_id: UUID of the user requesting verification.
            ip_address: Client IP for audit logging.

        Returns:
            An ``InternalTokenResult``; ``token`` is only set when
            ``AUTH_RETURN_INTERNAL_TOKENS=true``.

        Raises:
            NotFoundError: If the user does not exist.
        """
        user = self._repo.get_user_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found")
        token, expires_at = self._create_internal_token(
            user_id=user.id,
            purpose=EMAIL_VERIFY_PURPOSE,
            expires_delta=timedelta(
                minutes=self._settings.auth_email_verify_token_expire_minutes
            ),
            ip_address=ip_address,
        )
        self._repo.record_audit_event(
            event_type="auth.email_verify_requested",
            user_id=user.id,
            ip_address=ip_address,
        )
        # See request_password_reset above: spamming a warning here once per
        # request offered no signal beyond what the startup-time check provides.
        return InternalTokenResult(
            token=token if self._settings.auth_return_internal_tokens else None,
            expires_at=expires_at,
        )

    def verify_email(self, *, token: str) -> None:
        """Consume an email-verification token and mark the user as verified.

        Args:
            token: The single-use opaque verification token from the email link.

        Raises:
            InvalidTokenError: If the token is unknown, already used, or expired.
        """
        record = self._get_internal_token_or_raise(
            token=token, purpose=EMAIL_VERIFY_PURPOSE
        )
        if record.user_id is None:
            raise InvalidTokenError("Invalid token")
        self._repo.set_user_verified(record.user_id)
        self._repo.mark_internal_token_used(record.id)
        self.invalidate_principal_cache_for_user(record.user_id)
        self._repo.record_audit_event(
            event_type="auth.email_verified",
            user_id=record.user_id,
        )

    def _issue_tokens(
        self,
        user_id: UUID,
        *,
        ip_address: str | None,
        user_agent: str | None,
        family_id: UUID | None = None,
    ) -> tuple[IssuedTokens, Principal]:
        """Mint a new access/refresh token pair and persist the refresh token.

        Passing an existing ``family_id`` links the new token to a rotation
        chain; omitting it starts a new chain (fresh login).

        Raises:
            InvalidCredentialsError: If the user no longer exists.
            InactiveUserError: If the account has been deactivated.
        """
        principal = self._repo.get_principal(user_id)
        if principal is None:
            raise InvalidCredentialsError("Invalid credentials")
        if not principal.is_active:
            raise InactiveUserError("Inactive user")
        access_token, expires_in = self._tokens.issue(
            subject=user_id,
            roles=set(principal.roles),
            authz_version=principal.authz_version,
        )
        refresh_token = generate_opaque_token()
        self._repo.create_refresh_token(
            user_id=user_id,
            token_hash=hash_token(refresh_token),
            family_id=family_id or uuid4(),
            expires_at=datetime.now(timezone.utc)
            + timedelta(days=self._settings.auth_refresh_token_expire_days),
            created_ip=ip_address,
            user_agent=user_agent,
        )
        return (
            IssuedTokens(
                access_token=access_token,
                refresh_token=refresh_token,
                token_type="bearer",
                expires_in=expires_in,
            ),
            principal,
        )

    def _get_refresh_or_raise(self, refresh_token: str | None) -> RefreshToken:
        """Resolve a raw refresh token to its DB record or raise.

        Raises:
            InvalidTokenError: If the token is absent or not found in the DB.
        """
        if not refresh_token:
            raise InvalidTokenError("Invalid refresh token")
        record = self._repo.get_refresh_token_by_hash(hash_token(refresh_token))
        if record is None:
            raise InvalidTokenError("Invalid refresh token")
        return record

    def _create_internal_token(
        self,
        *,
        user_id: UUID,
        purpose: str,
        expires_delta: timedelta,
        ip_address: str | None,
    ) -> tuple[str, datetime]:
        """Generate, hash, and persist a single-use internal token.

        Returns:
            A tuple of ``(raw_token, expires_at)``. The raw token is returned
            to the caller for delivery; only its hash is stored in the DB.
        """
        token = generate_opaque_token()
        expires_at = datetime.now(timezone.utc) + expires_delta
        self._repo.create_internal_token(
            user_id=user_id,
            purpose=purpose,
            token_hash=hash_token(token),
            expires_at=expires_at,
            created_ip=ip_address,
        )
        return token, expires_at

    def _get_internal_token_or_raise(
        self, *, token: str, purpose: str
    ) -> InternalToken:
        """Resolve and validate a single-use internal token or raise.

        Rejects the token if it has already been used or has expired,
        giving the same error in all three cases to avoid leaking state.

        Raises:
            InvalidTokenError: If the token is not found, already used, or expired.
        """
        record = self._repo.get_internal_token(
            token_hash=hash_token(token), purpose=purpose
        )
        if (
            record is None
            or record.used_at is not None
            or record.expires_at <= datetime.now(timezone.utc)
        ):
            raise InvalidTokenError("Invalid token")
        return record


class RBACService:
    """Manages roles, permissions, and their assignments.

    Every mutation that changes who can do what also bumps the affected users'
    ``authz_version`` so stale access tokens are rejected on the next request.
    All operations are recorded in the audit log.
    """

    def __init__(
        self,
        *,
        repository: AuthRepositoryPort,
        cache: PrincipalCachePort | None = None,
    ) -> None:
        self._repo = repository
        self._cache = cache

    def list_roles(self, *, limit: int = 100, offset: int = 0) -> list[Role]:
        """Return roles ordered alphabetically with DB-level pagination."""
        return self._repo.list_roles(limit=limit, offset=offset)

    def list_users(self, *, limit: int = 100, offset: int = 0) -> list[User]:
        """Return users ordered by email with DB-level pagination."""
        return self._repo.list_users(limit=limit, offset=offset)

    def create_role(
        self,
        *,
        actor: Principal | None,
        name: str,
        description: str | None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> Role:
        """Create a new role with a normalised name.

        Args:
            actor: Principal performing the action; ``None`` during seeding.
            name: Role name; normalised to lowercase with underscores.
            description: Optional human-readable description.
            ip_address: Client IP for audit logging.
            user_agent: Client User-Agent for audit logging.

        Returns:
            The newly created ``RoleTable`` row.

        Raises:
            ConflictError: If the name is invalid or already exists.
        """
        normalized = normalize_role_name(name)
        if not is_role_name(normalized):
            raise ConflictError("Invalid role name")
        role = self._repo.create_role(name=normalized, description=description)
        if role is None:
            raise ConflictError("Role already exists")
        self._audit(
            "rbac.role_created",
            actor,
            ip_address,
            user_agent,
            {"role_id": str(role.id), "role_name": role.name},
        )
        return role

    def update_role(
        self,
        *,
        actor: Principal,
        role_id: UUID,
        name: str | None,
        description: str | None,
        is_active: bool | None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> Role:
        """Update mutable fields of a role.

        When ``is_active`` changes, all users holding the role have their
        ``authz_version`` bumped so the change takes effect immediately on
        their next request, without waiting for their tokens to expire.

        Args:
            actor: Principal performing the action.
            role_id: UUID of the role to update.
            name: New name, or ``None`` to leave unchanged.
            description: New description, or ``None`` to leave unchanged.
            is_active: New active flag, or ``None`` to leave unchanged.
            ip_address: Client IP for audit logging.
            user_agent: Client User-Agent for audit logging.

        Returns:
            The updated ``RoleTable`` row.

        Raises:
            NotFoundError: If the role does not exist.
            ConflictError: If the new name is invalid or already taken.
        """
        existing = self._repo.get_role(role_id)
        if existing is None:
            raise NotFoundError("Role not found")
        normalized_name = normalize_role_name(name) if name is not None else None
        if normalized_name is not None and not is_role_name(normalized_name):
            raise ConflictError("Invalid role name")
        updated = self._repo.update_role(
            role_id,
            name=normalized_name,
            description=description,
            is_active=is_active,
        )
        if updated is None:
            raise ConflictError("Role update failed")
        if is_active is not None and is_active != existing.is_active:
            # Bump authz_version for all holders of this role so their next
            # request fails the version check and they must re-authenticate,
            # making role activation/deactivation take effect immediately.
            self._repo.increment_authz_for_role_users(role_id)
            self._invalidate_role_users(role_id)
        self._audit(
            "rbac.role_updated",
            actor,
            ip_address,
            user_agent,
            {"role_id": str(role_id)},
        )
        return updated

    def list_permissions(
        self, *, limit: int = 100, offset: int = 0
    ) -> list[Permission]:
        """Return permissions ordered alphabetically with DB-level pagination."""
        return self._repo.list_permissions(limit=limit, offset=offset)

    def create_permission(
        self,
        *,
        actor: Principal | None,
        name: str,
        description: str | None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> Permission:
        """Create a new permission with a validated ``resource:action`` name.

        Args:
            actor: Principal performing the action; ``None`` during seeding.
            name: Permission name in ``resource:action`` format (e.g. ``"roles:read"``).
            description: Optional human-readable description.
            ip_address: Client IP for audit logging.
            user_agent: Client User-Agent for audit logging.

        Returns:
            The newly created ``PermissionTable`` row.

        Raises:
            ConflictError: If the name is invalid or already exists.
        """
        normalized = normalize_permission_name(name)
        if not is_permission_name(normalized):
            raise ConflictError("Invalid permission name")
        permission = self._repo.create_permission(
            name=normalized, description=description
        )
        if permission is None:
            raise ConflictError("Permission already exists")
        self._audit(
            "rbac.permission_created",
            actor,
            ip_address,
            user_agent,
            {"permission_id": str(permission.id), "permission_name": permission.name},
        )
        return permission

    def assign_role_permission(
        self,
        *,
        actor: Principal,
        role_id: UUID,
        permission_id: UUID,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """Grant a permission to a role and invalidate all affected tokens.

        All users holding the role have their ``authz_version`` bumped so the
        new permission is reflected immediately on their next request.

        Raises:
            NotFoundError: If the role or permission does not exist.
        """
        if not self._repo.assign_role_permission(role_id, permission_id):
            raise NotFoundError("Role or permission not found")
        # Invalidate existing tokens for all role members so the new permission
        # is not silently absent from in-flight access tokens.
        self._repo.increment_authz_for_role_users(role_id)
        self._invalidate_role_users(role_id)
        self._audit(
            "rbac.role_permission_added",
            actor,
            ip_address,
            user_agent,
            {"role_id": str(role_id), "permission_id": str(permission_id)},
        )

    def remove_role_permission(
        self,
        *,
        actor: Principal,
        role_id: UUID,
        permission_id: UUID,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """Revoke a permission from a role and invalidate all affected tokens.

        All users holding the role have their ``authz_version`` bumped so they
        can no longer exercise the revoked permission after their next request,
        without waiting for their access tokens to expire.

        Raises:
            NotFoundError: If the role-permission assignment does not exist.
        """
        if not self._repo.remove_role_permission(role_id, permission_id):
            raise NotFoundError("Role permission assignment not found")
        # Invalidate tokens immediately so users cannot keep exercising a
        # permission that was just revoked for the duration of the token TTL.
        self._repo.increment_authz_for_role_users(role_id)
        self._invalidate_role_users(role_id)
        self._audit(
            "rbac.role_permission_removed",
            actor,
            ip_address,
            user_agent,
            {"role_id": str(role_id), "permission_id": str(permission_id)},
        )

    def assign_user_role(
        self,
        *,
        actor: Principal,
        user_id: UUID,
        role_id: UUID,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """Grant a role to a user.

        The repository bumps the user's ``authz_version`` so the change
        takes effect on their next request.

        Raises:
            NotFoundError: If the user or role does not exist.
        """
        if not self._repo.assign_user_role(user_id, role_id):
            raise NotFoundError("User or role not found")
        self._invalidate_user(user_id)
        self._audit(
            "rbac.user_role_added",
            actor,
            ip_address,
            user_agent,
            {"target_user_id": str(user_id), "role_id": str(role_id)},
        )

    def remove_user_role(
        self,
        *,
        actor: Principal,
        user_id: UUID,
        role_id: UUID,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """Revoke a role from a user.

        Raises:
            NotFoundError: If the user-role assignment does not exist.
        """
        if not self._repo.remove_user_role(user_id, role_id):
            raise NotFoundError("User role assignment not found")
        self._invalidate_user(user_id)
        self._audit(
            "rbac.user_role_removed",
            actor,
            ip_address,
            user_agent,
            {"target_user_id": str(user_id), "role_id": str(role_id)},
        )

    def seed_initial_data(self) -> None:
        """Ensure the default permissions, roles, and role-permission mappings exist.

        Idempotent: skips any item that already exists. Safe to run on every
        deployment or startup without duplicating data.
        """
        permissions: dict[str, Permission] = {}
        for name, description in ALL_PERMISSIONS.items():
            permission = self._repo.get_permission_by_name(name)
            if permission is None:
                permission = self._repo.create_permission(
                    name=name, description=description
                )
            if permission is not None:
                permissions[name] = permission
        roles: dict[str, Role] = {}
        for role_name, description in ROLE_DESCRIPTIONS.items():
            role = self._repo.get_role_by_name(role_name)
            if role is None:
                role = self._repo.create_role(name=role_name, description=description)
            if role is not None:
                roles[role_name] = role
        for role_name, permission_names in ROLE_PERMISSIONS.items():
            role = roles.get(role_name)
            if role is None:
                continue
            for permission_name in permission_names:
                permission = permissions.get(permission_name)
                if permission is not None:
                    self._repo.assign_role_permission(role.id, permission.id)

    def bootstrap_super_admin(
        self,
        *,
        auth_service: AuthService,
        email: str,
        password: str,
    ) -> User:
        """Seed data and ensure the given account has the ``super_admin`` role.

        Creates the account if it does not exist yet. Intended for one-time
        bootstrap via the management CLI, not the public API, so it bypasses
        the rate limiter and audit trail of a normal registration.

        Args:
            auth_service: Used to register the account if it does not exist.
            email: Email of the super admin account to create or promote.
            password: Plaintext password (only used when creating a new account).

        Returns:
            The ``UserTable`` row with the ``super_admin`` role assigned.

        Raises:
            NotFoundError: If the ``super_admin`` role was not seeded.
        """
        self.seed_initial_data()
        normalized_email = normalize_email(email)
        user = self._repo.get_user_by_email(normalized_email)
        if user is None:
            try:
                user = auth_service.register(email=normalized_email, password=password)
            except DuplicateEmailError:
                # Two replicas racing at startup can both reach this branch.
                # The unique email constraint ensures only one INSERT succeeds;
                # the loser retries the lookup to find the row the winner wrote.
                user = self._repo.get_user_by_email(normalized_email)
                if user is None:
                    raise
        role = self._repo.get_role_by_name("super_admin")
        if role is None:
            raise NotFoundError("super_admin role not found")
        self._repo.assign_user_role(user.id, role.id)
        self._invalidate_user(user.id)
        self._repo.record_audit_event(
            event_type="rbac.super_admin_bootstrapped",
            user_id=user.id,
            metadata={"role_id": str(role.id)},
        )
        refreshed = self._repo.get_user_by_id(user.id)
        if refreshed is None:
            raise NotFoundError("User not found")
        return refreshed

    def list_audit_events(
        self,
        *,
        user_id: UUID | None = None,
        event_type: str | None = None,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[AuditEvent]:
        """Return filtered audit events for administrative inspection."""
        bounded_limit = max(1, min(limit, 500))
        return self._repo.list_audit_events(
            user_id=user_id,
            event_type=event_type,
            since=since,
            limit=bounded_limit,
        )

    def _invalidate_user(self, user_id: UUID) -> None:
        if self._cache is not None:
            self._cache.invalidate_user(user_id)

    def _invalidate_role_users(self, role_id: UUID) -> None:
        if self._cache is None:
            return
        for user_id in self._repo.list_user_ids_for_role(role_id):
            self._cache.invalidate_user(user_id)

    def _audit(
        self,
        event_type: str,
        actor: Principal | None,
        ip_address: str | None,
        user_agent: str | None,
        metadata: dict[str, Any],
    ) -> None:
        """Write an RBAC audit event, recording the acting principal if present.

        Embeds an ``actor`` snapshot (id, roles, permissions at the time of
        the action) so future audits can detect privilege escalation by
        comparing the actor's authority against the action they performed.
        """
        enriched = dict(metadata)
        if actor is not None:
            enriched["actor"] = {
                "user_id": str(actor.user_id),
                "roles": sorted(actor.roles),
                "permissions": sorted(actor.permissions),
            }
        self._repo.record_audit_event(
            event_type=event_type,
            user_id=actor.user_id if actor is not None else None,
            ip_address=ip_address,
            user_agent=user_agent,
            metadata=enriched,
        )


def ensure_permissions(principal: Principal, required: set[str], *, any_: bool) -> None:
    """Assert that a principal holds the required permissions or raise.

    Args:
        principal: The authenticated identity to check.
        required: The set of permission names to verify.
        any_: When ``True``, holding any one permission is sufficient.
            When ``False``, the principal must hold every permission in the set.

    Raises:
        PermissionDeniedError: If the check fails.
    """
    if any_:
        if principal.permissions.intersection(required):
            return
    elif required.issubset(principal.permissions):
        return
    _logger.warning(
        "event=rbac.permission_denied user_id=%s required_permission=%s timestamp=%s",
        principal.user_id,
        sorted(required),
        datetime.now(timezone.utc).isoformat(),
    )
    raise PermissionDeniedError("Not enough permissions")


def ensure_roles(principal: Principal, required: set[str]) -> None:
    """Assert that a principal holds at least one of the required roles or raise.

    Args:
        principal: The authenticated identity to check.
        required: The set of role names; membership in any one is sufficient.

    Raises:
        PermissionDeniedError: If the principal holds none of the required roles.
    """
    if required.intersection(principal.roles):
        return
    _logger.warning(
        "event=rbac.role_denied user_id=%s required_role=%s timestamp=%s",
        principal.user_id,
        sorted(required),
        datetime.now(timezone.utc).isoformat(),
    )
    raise PermissionDeniedError("Not enough roles")
