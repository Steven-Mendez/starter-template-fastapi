from __future__ import annotations

from typing import Protocol

from app_platform.shared.result import Result
from features.authentication.application.errors import AuthError


class LogoutUserPort(Protocol):
    def execute(self, refresh_token: str | None) -> Result[None, AuthError]: ...
