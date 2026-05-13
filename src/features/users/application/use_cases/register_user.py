"""Create a new user account.

Lives in the users feature now that the authentication/users split has
moved the ``User`` entity out of ``authentication``. The use case creates
the user row only; the password credential is written separately by the
authentication feature via its ``CredentialRepositoryPort``.
"""

from __future__ import annotations

from dataclasses import dataclass

from app_platform.shared.result import Result
from features.users.application.errors import UserError
from features.users.application.ports.user_port import UserPort
from features.users.domain.user import User


def _normalize_email(email: str) -> str:
    """Strip whitespace and lowercase an email address."""
    return email.strip().lower()


@dataclass(slots=True)
class RegisterUser:
    """Persist a new user."""

    _users: UserPort

    def execute(self, *, email: str) -> Result[User, UserError]:
        return self._users.create(email=_normalize_email(email))
