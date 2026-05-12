"""Read a user by primary key."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from src.features.users.application.errors import UserError
from src.features.users.application.ports.user_port import UserPort
from src.features.users.domain.user import User
from src.platform.shared.result import Err, Ok, Result


@dataclass(slots=True)
class GetUserById:
    """Return the user with the given id, or ``Err(NOT_FOUND)`` if absent."""

    _users: UserPort

    def execute(self, user_id: UUID) -> Result[User, UserError]:
        user = self._users.get_by_id(user_id)
        if user is None:
            return Err(UserError.NOT_FOUND)
        return Ok(user)
