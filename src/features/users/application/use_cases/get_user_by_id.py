"""Read a user by primary key."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app_platform.shared.result import Err, Ok, Result
from features.users.application.errors import UserError, UserNotFoundError
from features.users.application.ports.user_port import UserPort
from features.users.domain.user import User


@dataclass(slots=True)
class GetUserById:
    """Return the user with the given id, or ``Err(UserNotFoundError())`` if absent."""

    _users: UserPort

    def execute(self, user_id: UUID) -> Result[User, UserError]:
        user = self._users.get_by_id(user_id)
        if user is None:
            return Err(UserNotFoundError())
        return Ok(user)
