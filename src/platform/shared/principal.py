"""Platform-level authenticated identity contract.

Placing ``Principal`` in ``platform.shared`` lets any feature consume it
without importing from another feature, enforcing the cross-feature isolation
boundary enforced by Import Linter.
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
