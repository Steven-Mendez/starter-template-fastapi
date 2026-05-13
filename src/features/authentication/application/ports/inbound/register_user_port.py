from __future__ import annotations

from typing import Protocol

from app_platform.shared.result import Result
from features.authentication.application.errors import AuthError
from features.users.domain.user import User


class RegisterUserPort(Protocol):
    def execute(
        self,
        *,
        email: str,
        password: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> Result[User, AuthError]: ...
