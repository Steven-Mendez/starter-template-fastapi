"""Read a user by email."""

from __future__ import annotations

from dataclasses import dataclass

from src.features.users.application.errors import UserError
from src.features.users.application.ports.user_port import UserPort
from src.features.users.domain.user import User
from src.platform.shared.result import Err, Ok, Result


@dataclass(slots=True)
class GetUserByEmail:
    """Return the user with the given email (case-insensitive)."""

    _users: UserPort

    def execute(self, email: str) -> Result[User, UserError]:
        user = self._users.get_by_email(email.strip().lower())
        if user is None:
            return Err(UserError.NOT_FOUND)
        return Ok(user)
