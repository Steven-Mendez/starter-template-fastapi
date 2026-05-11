"""Idempotent register-or-lookup adapter for the authorization feature.

Wraps the existing ``RegisterUser`` use case and the auth repository's
``get_user_by_email`` lookup. The adapter is intentionally narrow: it
returns only the user id, never the full ``User`` aggregate, because
authorization has no business reading the rest of the user record.
"""

from __future__ import annotations

from uuid import UUID

from src.features.auth.application.errors import DuplicateEmailError
from src.features.auth.application.normalization import normalize_email
from src.features.auth.application.ports.outbound.auth_repository import (
    AuthRepositoryPort,
)
from src.features.auth.application.use_cases.auth.register_user import RegisterUser
from src.platform.shared.result import Err, Ok


class SQLModelUserRegistrarAdapter:
    """Returns an existing user id by email or registers a new account."""

    def __init__(
        self, *, repository: AuthRepositoryPort, register_user: RegisterUser
    ) -> None:
        self._repository = repository
        self._register_user = register_user

    def register_or_lookup(self, *, email: str, password: str) -> UUID:
        """Return the user id for ``email``, creating the account if missing.

        Idempotent on email. ``DuplicateEmailError`` from a concurrent
        write (two replicas racing during bootstrap) is swallowed by
        re-reading the row; any other auth-domain error propagates.
        """
        normalized = normalize_email(email)
        existing = self._repository.get_user_by_email(normalized)
        if existing is not None:
            return existing.id

        result = self._register_user.execute(email=normalized, password=password)
        match result:
            case Ok(value=created):
                return created.id
            case Err(error=exc):
                if isinstance(exc, DuplicateEmailError):
                    racer = self._repository.get_user_by_email(normalized)
                    if racer is not None:
                        return racer.id
                raise exc
