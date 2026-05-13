from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app_platform.shared.result import Result
from features.authentication.application.errors import AuthError


class LogoutAllPort(Protocol):
    def execute(
        self,
        *,
        user_id: UUID,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> Result[None, AuthError]: ...
