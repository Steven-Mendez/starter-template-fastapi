from __future__ import annotations

from typing import Protocol

from app_platform.shared.result import Result
from features.authentication.application.errors import AuthError


class ConfirmEmailVerificationPort(Protocol):
    def execute(self, *, token: str) -> Result[None, AuthError]: ...
