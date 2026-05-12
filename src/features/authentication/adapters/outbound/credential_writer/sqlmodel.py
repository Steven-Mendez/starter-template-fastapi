"""Adapter implementing the users feature's :class:`CredentialWriterPort`.

Hashes the supplied password with authentication's
:class:`PasswordService` and upserts a row into the ``credentials``
table via :class:`CredentialRepositoryPort`. Used by the users-feature
``SQLModelUserRegistrarAdapter`` to write the initial credential for
the bootstrap admin without users having to import authentication.
"""

from __future__ import annotations

from uuid import UUID

from src.features.authentication.application.crypto import PasswordService
from src.features.authentication.application.ports.outbound.auth_repository import (
    CredentialRepositoryPort,
)


class SQLModelCredentialWriterAdapter:
    """Hash + upsert; one row per call."""

    def __init__(
        self,
        *,
        credentials: CredentialRepositoryPort,
        password_service: PasswordService,
    ) -> None:
        self._credentials = credentials
        self._password_service = password_service

    def set_initial_password(self, *, user_id: UUID, password: str) -> None:
        self._credentials.upsert_credential(
            user_id=user_id,
            algorithm="argon2",
            hash=self._password_service.hash_password(password),
        )
