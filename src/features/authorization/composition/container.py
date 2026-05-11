"""Composition root for the authorization feature.

The container is constructed *after* the auth container so the three
outbound ports (``UserAuthzVersionPort``, ``UserRegistrarPort``,
``AuditPort``) can be passed in as already-built adapters. Kanban (and
any future feature that authorizes anything) consumes only the
``port`` and ``registry`` fields, never the inner adapters.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy.engine import Engine

from src.features.authorization.adapters.outbound.sqlmodel import (
    SQLModelAuthorizationAdapter,
)
from src.features.authorization.application.ports.authorization_port import (
    AuthorizationPort,
)
from src.features.authorization.application.ports.outbound import (
    AuditPort,
    UserAuthzVersionPort,
    UserRegistrarPort,
)
from src.features.authorization.application.registry import AuthorizationRegistry
from src.features.authorization.application.use_cases import BootstrapSystemAdmin


@dataclass(slots=True)
class AuthorizationContainer:
    """Bundle of every collaborator the authorization feature exposes."""

    port: AuthorizationPort
    registry: AuthorizationRegistry
    bootstrap_system_admin: BootstrapSystemAdmin
    shutdown: Callable[[], None]


def build_authorization_container(
    *,
    engine: Engine,
    user_authz_version: UserAuthzVersionPort,
    user_registrar: UserRegistrarPort,
    audit: AuditPort,
) -> AuthorizationContainer:
    """Wire the authorization container.

    Auth pre-registers only the ``system`` resource type. Other features
    register their own resource types from their composition roots after
    this container is built; the registry is sealed by ``main.py`` once
    every feature has contributed.
    """
    registry = AuthorizationRegistry()
    registry.register_resource_type(
        "system",
        actions={
            "manage_users": frozenset({"admin"}),
            "read_audit": frozenset({"admin"}),
        },
        hierarchy={"admin": frozenset({"admin"})},
    )

    port = SQLModelAuthorizationAdapter(engine, registry, user_authz_version)

    bootstrap = BootstrapSystemAdmin(
        _authorization=port,
        _user_registrar=user_registrar,
        _audit=audit,
    )

    def _shutdown() -> None:
        """No-op: the authorization feature owns no long-lived resources.

        The engine belongs to auth; the registry, port, and bootstrap
        use case are all in-memory objects with no background tasks or
        connections to release.
        """

    return AuthorizationContainer(
        port=port,
        registry=registry,
        bootstrap_system_admin=bootstrap,
        shutdown=_shutdown,
    )
