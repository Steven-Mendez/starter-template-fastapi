"""Platform-level authenticated identity contract.

Placing ``Principal`` in ``platform.shared`` lets any feature consume it
without importing from another feature, enforcing the cross-feature isolation
boundary enforced by Import Linter.

Authorization is no longer carried on the principal: under ReBAC, every
check goes through ``AuthorizationPort`` against the relationships store.
The principal carries only the identity and lifecycle flags needed by
features that don't ask the authorization engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class Principal:
    """Authenticated identity resolved for the duration of a single request.

    ``frozen=True`` makes the principal immutable so request handlers cannot
    accidentally mutate the resolved identity between dependency calls.

    Attributes:
        user_id: Stable UUID of the underlying user account.
        email: Normalised email of the account.
        is_active: Whether the account is enabled.
        is_verified: Whether the account's email has been verified.
        authz_version: Monotonic counter compared against the JWT claim on
            every request. Bumping it server-side invalidates any token
            previously issued for this user without waiting for expiry.
            Bumped by every relationship write/delete affecting this user.
    """

    user_id: UUID
    email: str
    is_active: bool
    is_verified: bool
    authz_version: int
