"""Application-layer value objects shared across the auth feature.

These types are the contract between the auth services, the HTTP layer, and
the persistence layer. Keeping them as frozen dataclasses guarantees that an
identity or token payload resolved once cannot be mutated downstream.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

# Principal now lives in the platform layer so any feature can consume it
# without importing from the auth feature.  The re-export here keeps existing
# intra-auth import paths working; callers outside auth should import directly
# from ``platform.shared.principal``.


@dataclass(frozen=True, slots=True)
class AccessTokenPayload:
    """Verified subset of JWT claims used by the application layer.

    Only the claims that business logic actually consumes are exposed; the
    raw JWT dict stays inside the token service so the JWT format remains
    an implementation detail. Under ReBAC, no roles or permissions are
    embedded in the token — every authorization check goes through
    ``AuthorizationPort`` against the relationships store.

    Attributes:
        subject: User UUID extracted from the ``sub`` claim.
        authz_version: Authorization version embedded at issuance, used to
            detect tokens issued before a relevant relationship change.
        expires_at: Absolute expiration timestamp from the ``exp`` claim.
        token_id: Unique JWT identifier (``jti``), useful for logging and
            future per-token revocation.
    """

    subject: UUID
    authz_version: int
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
