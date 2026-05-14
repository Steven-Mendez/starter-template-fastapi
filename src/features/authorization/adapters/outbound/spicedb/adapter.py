"""Structural placeholder for a SpiceDB-backed AuthorizationPort.

The class implements the same five methods as the in-repo adapter but
raises ``NotImplementedError`` from each. It exists so a reader can
verify the AuthorizationPort is an honest seam: the SpiceDB swap is
this single adapter, not an engine rewrite.

A live implementation would:

* Translate the live ``AuthorizationRegistry`` contents into a ``.zed``
  schema once at startup (or load it from a checked-in file).
* Issue ``CheckPermission`` for ``check`` (one round trip).
* Issue ``LookupResources`` / ``LookupSubjects`` for the corresponding
  port methods.
* Issue ``WriteRelationships`` / ``DeleteRelationships`` for writes.

See ``README.md`` for the mapping and the example schema.
"""

from __future__ import annotations

from uuid import UUID

from features.authorization.application.ports.authorization_port import (
    LOOKUP_DEFAULT_LIMIT,
)
from features.authorization.application.types import Relationship


class SpiceDBAuthorizationAdapter:  # pragma: no cover
    """Stub adapter; every method raises ``NotImplementedError``.

    A real implementation would take a SpiceDB client (gRPC) at
    construction and translate each port call into the corresponding
    SpiceDB API request.
    """

    _STUB_MESSAGE = (
        "SpiceDB integration is a stub; see "
        "src/features/authorization/adapters/outbound/spicedb/README.md "
        "for the API mapping and `.zed` schema."
    )

    def check(  # pragma: no cover
        self,
        *,
        user_id: UUID,
        action: str,
        resource_type: str,
        resource_id: str,
    ) -> bool:
        raise NotImplementedError(self._STUB_MESSAGE)

    def lookup_resources(  # pragma: no cover
        self,
        *,
        user_id: UUID,
        action: str,
        resource_type: str,
        limit: int = LOOKUP_DEFAULT_LIMIT,
    ) -> list[str]:
        raise NotImplementedError(self._STUB_MESSAGE)

    def lookup_subjects(  # pragma: no cover
        self,
        *,
        resource_type: str,
        resource_id: str,
        relation: str,
        limit: int | None = None,
    ) -> list[UUID]:
        raise NotImplementedError(self._STUB_MESSAGE)

    def write_relationships(  # pragma: no cover
        self, tuples: list[Relationship]
    ) -> None:
        raise NotImplementedError(self._STUB_MESSAGE)

    def delete_relationships(  # pragma: no cover
        self, tuples: list[Relationship]
    ) -> None:
        raise NotImplementedError(self._STUB_MESSAGE)
