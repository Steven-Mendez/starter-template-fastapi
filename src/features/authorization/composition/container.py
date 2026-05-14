"""Composition root for the authorization feature.

The container is constructed *after* the auth container so the three
outbound ports (``UserAuthzVersionPort``, ``UserRegistrarPort``,
``AuditPort``) can be passed in as already-built adapters. Any feature
that authorizes anything consumes only the ``port`` and ``registry``
fields, never the inner adapters.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy.engine import Engine

from features.authorization.adapters.outbound.sqlmodel import (
    SQLModelAuthorizationAdapter,
)
from features.authorization.application.ports.authorization_port import (
    AuthorizationPort,
)
from features.authorization.application.ports.outbound import (
    AuditPort,
    CredentialVerifierPort,
    PrincipalCacheInvalidatorPort,
    UserAuthzVersionPort,
    UserRegistrarPort,
)
from features.authorization.application.registry import AuthorizationRegistry
from features.authorization.application.use_cases import BootstrapSystemAdmin


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
    credential_verifier: CredentialVerifierPort,
    principal_cache_invalidator: PrincipalCacheInvalidatorPort,
    promote_existing: bool = False,
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
        _credential_verifier=credential_verifier,
        _audit=audit,
        _principal_cache_invalidator=principal_cache_invalidator,
        _promote_existing=promote_existing,
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
