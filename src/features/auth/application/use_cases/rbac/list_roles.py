from __future__ import annotations

from dataclasses import dataclass

from src.features.auth.application.errors import AuthError
from src.features.auth.application.ports.outbound.auth_repository import (
    AuthRepositoryPort,
)
from src.features.auth.domain.models import Role
from src.platform.shared.result import Ok, Result


@dataclass(slots=True)
class ListRoles:
    _repository: AuthRepositoryPort

    def execute(
        self, *, limit: int = 100, offset: int = 0
    ) -> Result[list[Role], AuthError]:
        return Ok(self._repository.list_roles(limit=limit, offset=offset))
