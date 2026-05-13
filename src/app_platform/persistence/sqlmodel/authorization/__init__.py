"""Platform-owned SQLModel persistence for cross-feature authorization data.

The ``relationships`` table is referenced by every feature's authz
checks at request time, so its definition lives in the platform layer
rather than inside any one feature. The :mod:`authorization` feature
reads and writes the table through an adapter; other features see the
table only through the ``AuthorizationPort``.
"""

from __future__ import annotations

from app_platform.persistence.sqlmodel.authorization.models import RelationshipTable

__all__ = ["RelationshipTable"]
