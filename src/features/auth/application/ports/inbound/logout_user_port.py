from __future__ import annotations

from typing import Protocol

from src.features.auth.application.errors import AuthError
from src.platform.shared.result import Result


class LogoutUserPort(Protocol):
    def execute(self, refresh_token: str | None) -> Result[None, AuthError]: ...
