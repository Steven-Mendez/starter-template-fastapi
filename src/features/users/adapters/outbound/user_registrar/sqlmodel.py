"""Idempotent register-or-lookup adapter for the authorization feature.

Implements the authorization feature's ``UserRegistrarPort``. The
adapter takes the users feature's :class:`UserPort` and a
:class:`CredentialWriterPort` (implemented by authentication so the
initial password can be persisted into the ``credentials`` table without
this module having to import authentication directly).
"""

from __future__ import annotations

from uuid import UUID

from app_platform.shared.result import Err, Ok
from features.users.application.errors import UserAlreadyExistsError
from features.users.application.ports.credential_writer_port import (
    CredentialWriterPort,
)
from features.users.application.ports.user_port import UserPort


class SQLModelUserRegistrarAdapter:
    """Returns an existing user id by email or registers a new account."""

    def __init__(
        self,
        *,
        users: UserPort,
        credential_writer: CredentialWriterPort,
    ) -> None:
        self._users = users
        self._credential_writer = credential_writer

    def register_or_lookup(self, *, email: str, password: str) -> UUID:
        """Return the user id for ``email``, creating the account if missing.

        Idempotent on email. A concurrent write that races into a
        duplicate-email error is resolved by re-reading the row. When a
        new account is created the supplied password is also written as
        the initial credential.
        """
        normalized = email.strip().lower()
        existing = self._users.get_by_email(normalized)
        if existing is not None:
            return existing.id

        result = self._users.create(email=normalized)
        match result:
            case Ok(value=created):
                self._credential_writer.set_initial_password(
                    user_id=created.id, password=password
                )
                return created.id
            case Err(error=err):
                if isinstance(err, UserAlreadyExistsError):
                    racer = self._users.get_by_email(normalized)
                    if racer is not None:
                        return racer.id
                raise RuntimeError(f"User registration failed: {err}")

    def lookup_by_email(self, *, email: str) -> UUID | None:
        """Return the user id for ``email`` if a row exists, else ``None``.

        Side-effect-free counterpart to :meth:`register_or_lookup` that
        ``BootstrapSystemAdmin`` calls first so it can branch on
        existence without creating a row when no account is found.
        """
        normalized = email.strip().lower()
        existing = self._users.get_by_email(normalized)
        if existing is None:
            return None
        return existing.id
