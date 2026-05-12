from __future__ import annotations

from typing import Protocol

from src.features.authentication.application.errors import AuthError
from src.platform.shared.result import Result


class ConfirmPasswordResetPort(Protocol):
    def execute(self, *, token: str, new_password: str) -> Result[None, AuthError]: ...
