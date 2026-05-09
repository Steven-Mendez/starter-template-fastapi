from __future__ import annotations

from typing import Protocol
from uuid import UUID

from src.features.auth.application.errors import AuthError
from src.platform.shared.result import Result


class LogoutAllPort(Protocol):
    def execute(
        self,
        *,
        user_id: UUID,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> Result[None, AuthError]: ...
