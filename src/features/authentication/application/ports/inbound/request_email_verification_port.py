from __future__ import annotations

from typing import Protocol
from uuid import UUID

from src.features.authentication.application.errors import AuthError
from src.features.authentication.application.types import InternalTokenResult
from src.platform.shared.result import Result


class RequestEmailVerificationPort(Protocol):
    def execute(
        self,
        *,
        user_id: UUID,
        ip_address: str | None = None,
    ) -> Result[InternalTokenResult, AuthError]: ...
