"""Authorization feature: ReBAC engine, registry, and bootstrap use case.

The feature owns the ``AuthorizationPort`` Protocol, the runtime
``AuthorizationRegistry`` that lets other features contribute their
resource types, the SQLModel-backed engine adapter, the SpiceDB stub,
and the ``BootstrapSystemAdmin`` use case. It depends on the auth
feature only through the three small outbound ports defined under
``application/ports/outbound/`` (``UserAuthzVersionPort``,
``UserRegistrarPort``, ``AuditPort``).
"""

from __future__ import annotations

from src.features.authorization.application import (
    AuthorizationPort,
    AuthorizationRegistry,
    BootstrapSystemAdmin,
    Relationship,
)

__all__ = [
    "AuthorizationPort",
    "AuthorizationRegistry",
    "BootstrapSystemAdmin",
    "Relationship",
]
