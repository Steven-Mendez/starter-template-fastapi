from __future__ import annotations

from dataclasses import dataclass

from src.features.authentication.application.errors import AuthError
from src.features.authentication.application.ports.outbound.auth_repository import (
    AuthRepositoryPort,
)
from src.features.authentication.domain.models import User
from src.platform.shared.result import Ok, Result


@dataclass(slots=True)
class ListUsers:
    _repository: AuthRepositoryPort

    def execute(
        self, *, limit: int = 100, offset: int = 0
    ) -> Result[list[User], AuthError]:
        return Ok(self._repository.list_users(limit=limit, offset=offset))
