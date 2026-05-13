"""Bootstrap the first system administrator under the ReBAC model.

Composes four outbound ports: ``UserRegistrarPort`` to make sure the
configured account exists, ``AuthorizationPort`` to write the
``system:main#admin`` tuple, ``AuditPort`` to record the assignment,
and ``PrincipalCacheInvalidatorPort`` to drop any cached principal
entries for the bootstrapped user so the new admin permission is
honoured on the very next request.

The relationships table's unique constraint keeps re-runs idempotent.

This use case lives in the authorization feature because it operates on
the authorization domain (the system-admin relationship). The fact that
it needs a user is incidental and is routed through a port so
authorization never imports from auth.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import UUID

from app_platform.observability.tracing import traced
from features.authorization.application.ports.authorization_port import (
    AuthorizationPort,
)
from features.authorization.application.ports.outbound import (
    AuditPort,
    PrincipalCacheInvalidatorPort,
    UserRegistrarPort,
)
from features.authorization.application.types import Relationship

_logger = logging.getLogger(__name__)


@dataclass(slots=True)
class BootstrapSystemAdmin:
    """Ensure the configured account exists and holds ``system:main#admin``."""

    _authorization: AuthorizationPort
    _user_registrar: UserRegistrarPort
    _audit: AuditPort
    _principal_cache_invalidator: PrincipalCacheInvalidatorPort

    @traced("authz.bootstrap_system_admin")
    def execute(self, *, email: str, password: str) -> UUID:
        """Return the bootstrapped user's id.

        After the relationship write returns, drops any cached principal
        entries for the bootstrapped user. Cache invalidation is
        best-effort — a transport failure (e.g., Redis blip) is logged
        at WARNING and swallowed so the durable success (the DB-side
        relationship + ``authz_version`` bump committed atomically) is
        not undone by an optimisation failure.

        Raises:
            AuthError: If registration fails for a reason other than
                ``DuplicateEmailError`` (the registrar swallows that
                via its idempotent contract).
        """
        user_id = self._user_registrar.register_or_lookup(
            email=email, password=password
        )
        self._authorization.write_relationships(
            [
                Relationship(
                    resource_type="system",
                    resource_id="main",
                    relation="admin",
                    subject_type="user",
                    subject_id=str(user_id),
                )
            ]
        )
        try:
            self._principal_cache_invalidator.invalidate_user(user_id)
        except Exception as exc:
            _logger.warning(
                "event=authz.cache_invalidation.failed user_id=%s reason=%r",
                user_id,
                exc,
            )
        self._audit.record(
            "authz.bootstrap_admin_assigned",
            user_id=user_id,
        )
        return user_id
