from __future__ import annotations

from typing import Protocol

from src.features.auth.application.errors import AuthError
from src.features.auth.domain.models import User
from src.platform.shared.result import Result


class RegisterUserPort(Protocol):
    def execute(
        self,
        *,
        email: str,
        password: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> Result[User, AuthError]: ...
