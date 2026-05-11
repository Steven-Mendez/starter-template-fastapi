"""Bootstrap the first system administrator under the ReBAC model.

Composes three outbound ports: ``UserRegistrarPort`` to make sure the
configured account exists, ``AuthorizationPort`` to write the
``system:main#admin`` tuple, and ``AuditPort`` to record the assignment.
The relationships table's unique constraint keeps re-runs idempotent.

This use case lives in the authorization feature because it operates on
the authorization domain (the system-admin relationship). The fact that
it needs a user is incidental and is routed through a port so
authorization never imports from auth.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from src.features.authorization.application.ports.authorization_port import (
    AuthorizationPort,
)
from src.features.authorization.application.ports.outbound import (
    AuditPort,
    UserRegistrarPort,
)
from src.features.authorization.application.types import Relationship


@dataclass(slots=True)
class BootstrapSystemAdmin:
    """Ensure the configured account exists and holds ``system:main#admin``."""

    _authorization: AuthorizationPort
    _user_registrar: UserRegistrarPort
    _audit: AuditPort

    def execute(self, *, email: str, password: str) -> UUID:
        """Return the bootstrapped user's id.

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
        self._audit.record(
            "authz.bootstrap_admin_assigned",
            user_id=user_id,
        )
        return user_id
