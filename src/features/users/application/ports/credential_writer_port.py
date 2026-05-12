"""Outbound port: write the initial password credential for a new user.

The users feature owns the ``User`` row but not the password hash, which
lives in the authentication feature's ``credentials`` table. The bootstrap
flow (``BootstrapSystemAdmin``) creates the user via :class:`UserPort` and
then writes the credential through this port, which authentication
implements. Defining the port in the users feature keeps the dependency
direction one-way: authentication imports from users, never the reverse.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID


class CredentialWriterPort(Protocol):
    """Write the initial password credential for an existing user."""

    def set_initial_password(self, *, user_id: UUID, password: str) -> None:
        """Hash and persist ``password`` as the user's primary credential.

        Idempotent: calling twice with the same user replaces the
        previous credential. Implementations SHALL store the hash in
        authentication's ``credentials`` table under ``algorithm='argon2'``.
        """
        ...
