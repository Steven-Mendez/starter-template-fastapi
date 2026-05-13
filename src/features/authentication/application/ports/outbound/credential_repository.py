"""Outbound port: persistence operations for password credentials.

The authentication feature owns the ``credentials`` table, which is the
sole storage for password hashes. The users feature exposes only
profile-shaped state.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from features.authentication.domain.models import Credential


class CredentialRepositoryPort(Protocol):
    """Read/write operations over the password credential store."""

    def get_for_user(
        self, user_id: UUID, *, algorithm: str = "argon2"
    ) -> Credential | None:
        """Return the credential for ``user_id`` and ``algorithm``, or ``None``."""
        ...

    def upsert(
        self,
        *,
        user_id: UUID,
        algorithm: str,
        hash: str,
    ) -> Credential:
        """Insert a new credential row or replace the existing one in place.

        The ``(user_id, algorithm)`` pair is unique; an upsert keeps the
        flow idempotent when registration retries or when a password
        reset re-runs after a transient failure.
        """
        ...
