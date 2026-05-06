"""Application-layer value objects shared across the auth feature.

These types are the contract between the auth services, the HTTP layer, and
the persistence layer. Keeping them as frozen dataclasses guarantees that an
identity or token payload resolved once cannot be mutated downstream.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class Principal:
    """Authenticated identity resolved for the duration of a single request.

    ``frozen=True`` makes the principal immutable so request handlers cannot
    accidentally mutate the resolved identity between dependency calls.

    Attributes:
        user_id: Stable UUID of the underlying user account.
        email: Normalised email of the account.
        is_active: Whether the account is enabled. Inactive principals are
            rejected before any business logic runs.
        is_verified: Whether the account's email has been verified.
        authz_version: Monotonic counter compared against the JWT claim on
            every request. Bumping it server-side invalidates any token
            previously issued for this user without waiting for expiry.
        roles: Role names currently assigned to the user.
        permissions: Flattened set of permissions resolved from the user's
            active roles, used for fine-grained access checks.
    """

    user_id: UUID
    email: str
    is_active: bool
    is_verified: bool
    authz_version: int
    roles: frozenset[str]
    permissions: frozenset[str]


@dataclass(frozen=True, slots=True)
class AccessTokenPayload:
    """Verified subset of JWT claims used by the application layer.

    Only the claims that business logic actually consumes are exposed; the
    raw JWT dict stays inside the token service so the JWT format remains
    an implementation detail.

    Attributes:
        subject: User UUID extracted from the ``sub`` claim.
        authz_version: Authorization version embedded at issuance, used to
            detect tokens whose permission set is now stale.
        roles: Roles snapshotted at issuance, in deterministic order.
        expires_at: Absolute expiration timestamp from the ``exp`` claim.
        token_id: Unique JWT identifier (``jti``), useful for logging and
            future per-token revocation.
    """

    subject: UUID
    authz_version: int
    roles: tuple[str, ...]
    expires_at: datetime
    token_id: str


@dataclass(frozen=True, slots=True)
class IssuedTokens:
    """Pair of access and refresh tokens returned to the client on login or refresh.

    Attributes:
        access_token: Encoded JWT presented in the ``Authorization`` header.
        refresh_token: Opaque, single-use refresh token persisted as a hash.
        token_type: Always ``"bearer"``; included for OAuth-style clients.
        expires_in: Lifetime of ``access_token`` in seconds.
    """

    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int


@dataclass(frozen=True, slots=True)
class InternalTokenResult:
    """Outcome of issuing a single-use internal token (password reset / email verify).

    The raw token is intentionally kept out of API responses in production so
    reset and verification flows do not leak tokens through HTTP. ``token`` is
    only populated when ``AUTH_RETURN_INTERNAL_TOKENS=true`` (local
    development and tests).

    Attributes:
        token: The raw single-use token, or ``None`` when the account does
            not exist or returning internal tokens is disabled.
        expires_at: Absolute expiration of the token, or ``None`` when no
            token was issued.
    """

    token: str | None
    expires_at: datetime | None
