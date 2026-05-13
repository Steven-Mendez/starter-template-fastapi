from __future__ import annotations

from typing import Protocol

from app_platform.shared.principal import Principal
from app_platform.shared.result import Result
from features.authentication.application.errors import AuthError


class ResolvePrincipalFromAccessTokenPort(Protocol):
    def execute(self, token: str) -> Result[Principal, AuthError]: ...
