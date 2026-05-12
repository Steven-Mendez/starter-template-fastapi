"""ListThings use case: filters by authorization."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from src.features._template.application.ports.outbound.thing_repository import (
    ThingRepositoryPort,
)
from src.features._template.domain.models.thing import Thing
from src.features.authorization.application.ports.authorization_port import (
    AuthorizationPort,
)


@dataclass(frozen=True, slots=True)
class ListThingsQuery:
    user_id: UUID


@dataclass(slots=True)
class ListThingsUseCase:
    """Return only the things the caller has at least ``read`` access to.

    Filters at the authorization layer via ``AuthorizationPort.lookup_resources``
    rather than fetching all things and post-filtering, which is both
    faster and the only correct approach once the dataset grows beyond
    what fits in memory.
    """

    repository: ThingRepositoryPort
    authorization: AuthorizationPort

    def execute(self, query: ListThingsQuery) -> list[Thing]:
        ids = self.authorization.lookup_resources(
            user_id=query.user_id,
            action="read",
            resource_type="thing",
        )
        if not ids:
            return []
        return self.repository.list_by_ids([UUID(i) for i in ids])
