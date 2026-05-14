"""List users (paginated). Used by the admin HTTP route ``GET /admin/users``."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app_platform.shared.result import Ok, Result
from features.users.application.errors import UserError
from features.users.application.ports.user_port import UserPort
from features.users.domain.user import User


@dataclass(slots=True)
class ListUsers:
    """Return a page of users for system-admin inspection.

    Pagination is keyset-based on ``(created_at, id)``: clients pass the
    last row's tuple as ``cursor`` to fetch the next page. The route
    layer is responsible for encoding/decoding the cursor as base64 so
    the application contract stays in domain terms.
    """

    _users: UserPort

    def execute(
        self,
        *,
        cursor: tuple[datetime, UUID] | None = None,
        limit: int = 100,
    ) -> Result[list[User], UserError]:
        bounded_limit = max(1, min(limit, 500))
        return Ok(self._users.list_paginated(cursor=cursor, limit=bounded_limit))
