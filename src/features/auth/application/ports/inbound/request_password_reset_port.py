from __future__ import annotations

from typing import Protocol

from src.features.auth.application.errors import AuthError
from src.features.auth.application.types import InternalTokenResult
from src.platform.shared.result import Result


class RequestPasswordResetPort(Protocol):
    def execute(
        self,
        *,
        email: str,
        ip_address: str | None = None,
    ) -> Result[InternalTokenResult, AuthError]: ...
