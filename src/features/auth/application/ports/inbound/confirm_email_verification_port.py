from __future__ import annotations

from typing import Protocol

from src.features.auth.application.errors import AuthError
from src.platform.shared.result import Result


class ConfirmEmailVerificationPort(Protocol):
    def execute(self, *, token: str) -> Result[None, AuthError]: ...
