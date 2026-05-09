"""User-facing authentication flows: registration, login, token rotation.

Handles the full lifecycle of a user session — creating accounts, verifying
credentials, issuing/rotating/revoking tokens, and resetting passwords. Every
flow is audited; domain errors surface as ``AuthError`` subclasses for the
HTTP adapter to translate into appropriate status codes.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
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
    DuplicateEmailError,
    EmailNotVerifiedError,
    InactiveUserError,
    InvalidCredentialsError,
    InvalidTokenError,
    NotFoundError,
    StaleTokenError,
    TokenAlreadyUsedError,
)
from src.features.auth.application.jwt_tokens import AccessTokenService
from src.features.auth.application.normalization import (
    normalize_email,
    normalize_role_name,
)
from src.features.auth.application.ports.outbound.auth_repository import (
    AuthRepositoryPort,
)
from src.features.auth.application.types import (
    InternalTokenResult,
    IssuedTokens,
    Principal,
)
from src.features.auth.domain.models import InternalToken, RefreshToken, User
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
