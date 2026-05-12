from __future__ import annotations

from typing import Protocol

from src.features.authentication.application.errors import AuthError
from src.platform.shared.principal import Principal
from src.platform.shared.result import Result


class ResolvePrincipalFromAccessTokenPort(Protocol):
    def execute(self, token: str) -> Result[Principal, AuthError]: ...
