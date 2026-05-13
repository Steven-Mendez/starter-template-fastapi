from __future__ import annotations

from typing import Protocol

from app_platform.shared.principal import Principal
from app_platform.shared.result import Result
from features.authentication.application.errors import AuthError
from features.authentication.application.types import IssuedTokens


class RefreshTokenPort(Protocol):
    def execute(
        self,
        *,
        refresh_token: str | None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> Result[tuple[IssuedTokens, Principal], AuthError]: ...
