from __future__ import annotations

from typing import Protocol

from app_platform.shared.result import Result
from features.authentication.application.errors import AuthError
from features.authentication.application.types import InternalTokenResult


class RequestPasswordResetPort(Protocol):
    def execute(
        self,
        *,
        email: str,
        ip_address: str | None = None,
    ) -> Result[InternalTokenResult, AuthError]: ...
