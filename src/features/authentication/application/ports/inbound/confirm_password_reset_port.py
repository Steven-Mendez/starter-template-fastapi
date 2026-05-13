from __future__ import annotations

from typing import Protocol

from app_platform.shared.result import Result
from features.authentication.application.errors import AuthError


class ConfirmPasswordResetPort(Protocol):
    def execute(self, *, token: str, new_password: str) -> Result[None, AuthError]: ...
