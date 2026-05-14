"""Port for registering or looking up a user by email.

Used only by ``BootstrapSystemAdmin`` — every other authorization
operation references an already-existing user_id and never needs to
create one. The port is intentionally narrow: it does not expose any
other user-shaped state to authorization.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID


class UserRegistrarPort(Protocol):
    """Idempotent register-or-lookup contract for the auth feature."""

    def register_or_lookup(self, *, email: str, password: str) -> UUID:
        """Return the user id for ``email``, creating the account if needed.

        SHALL be idempotent on email: re-running with the same email
        returns the same id and SHALL NOT raise ``DuplicateEmailError``.
        SHALL raise an ``AuthError`` subclass on any other failure (e.g.,
        a password that fails policy validation on first registration).
        """
        ...

    def lookup_by_email(self, *, email: str) -> UUID | None:
        """Return the user id for ``email`` if a user exists, else ``None``.

        Side-effect-free lookup used by ``BootstrapSystemAdmin`` to
        decide between the create-and-grant, idempotent no-op,
        refuse-existing, and promote-existing branches without
        accidentally creating a row on the not-found path. SHALL NOT
        raise on a missing user — only on infrastructure failures.
        """
        ...
