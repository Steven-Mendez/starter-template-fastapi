from __future__ import annotations

from typing import Protocol

from src.features.auth.application.errors import AuthError
from src.features.auth.application.types import IssuedTokens
from src.platform.shared.principal import Principal
from src.platform.shared.result import Result


class LoginUserPort(Protocol):
    def execute(
        self,
        *,
        email: str,
        password: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> Result[tuple[IssuedTokens, Principal], AuthError]: ...
