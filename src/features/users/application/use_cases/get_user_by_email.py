"""Read a user by email."""

from __future__ import annotations

from dataclasses import dataclass

from app_platform.shared.result import Err, Ok, Result
from features.users.application.errors import UserError, UserNotFoundError
from features.users.application.ports.user_port import UserPort
from features.users.domain.user import User


@dataclass(slots=True)
class GetUserByEmail:
    """Return the user with the given email (case-insensitive)."""

    _users: UserPort

    def execute(self, email: str) -> Result[User, UserError]:
        user = self._users.get_by_email(email.strip().lower())
        if user is None:
            return Err(UserNotFoundError())
        return Ok(user)
