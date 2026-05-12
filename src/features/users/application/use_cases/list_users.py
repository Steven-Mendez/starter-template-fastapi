"""List users (paginated). Used by the admin HTTP route ``GET /admin/users``."""

from __future__ import annotations

from dataclasses import dataclass

from src.features.users.application.errors import UserError
from src.features.users.application.ports.user_port import UserPort
from src.features.users.domain.user import User
from src.platform.shared.result import Ok, Result


@dataclass(slots=True)
class ListUsers:
    """Return a page of users for system-admin inspection."""

    _users: UserPort

    def execute(
        self, *, limit: int = 100, offset: int = 0
    ) -> Result[list[User], UserError]:
        return Ok(self._users.list_paginated(limit=limit, offset=offset))
