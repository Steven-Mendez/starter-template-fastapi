"""Outbound ports the authorization feature requires from its environment.

Authorization owns ReBAC engine logic and the relationships table; it
relies on other features for everything user-shaped. The three ports
here are the only seams through which authorization touches state that
lives outside the feature.

* :class:`UserAuthzVersionPort` — auth implements; called after every
  relationship write affecting a user subject so cached principals
  invalidate on the next request.
* :class:`UserRegistrarPort` — auth implements; called by
  ``BootstrapSystemAdmin`` to ensure a user exists before writing the
  ``system:main#admin`` tuple.
* :class:`AuditPort` — auth implements; receives ``authz.*`` events
  (e.g., ``authz.bootstrap_admin_assigned``) for the audit log that
  auth already maintains.
"""

from __future__ import annotations

from features.authorization.application.ports.outbound.audit_port import (
    AuditPort,
)
from features.authorization.application.ports.outbound.user_authz_version_port import (  # noqa: E501
    UserAuthzVersionPort,
)
from features.authorization.application.ports.outbound.user_registrar_port import (
    UserRegistrarPort,
)

__all__ = ["AuditPort", "UserAuthzVersionPort", "UserRegistrarPort"]
