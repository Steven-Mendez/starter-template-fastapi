"""Cross-feature DTO protocols for the users feature.

Defines minimal structural-typing contracts other features can depend on
without importing the concrete :class:`features.users.domain.user.User`
entity. The Protocol form keeps cross-feature coupling at the shape
level — any object exposing the named attributes satisfies the contract.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID


class UserSnapshot(Protocol):
    """Read-only view of the user attributes other features rely on.

    The shape mirrors the subset of :class:`features.users.domain.user.User`
    that the authentication feature reads when building a :class:`Principal`
    after a token rotation. Declared as a Protocol so the authentication
    feature stays decoupled from the concrete entity and so structural
    failures surface at the call site instead of inside the helper.
    """

    @property
    def id(self) -> UUID: ...

    @property
    def email(self) -> str: ...

    @property
    def is_active(self) -> bool: ...

    @property
    def is_verified(self) -> bool: ...

    @property
    def authz_version(self) -> int: ...
