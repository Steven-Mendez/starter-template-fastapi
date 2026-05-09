"""Pure authorization checks: permission and role enforcement.

These functions operate on already-resolved principals and enforce
access-control rules without any I/O. They sit in the application layer
so both the HTTP adapter and internal services can call them without
creating cross-layer imports.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from src.features.auth.application.errors import PermissionDeniedError
from src.features.auth.application.types import Principal

_logger = logging.getLogger(__name__)


def ensure_permissions(principal: Principal, required: set[str], *, any_: bool) -> None:
    """Assert that a principal holds the required permissions or raise.

    Args:
        principal: The authenticated identity to check.
        required: The set of permission names to verify.
        any_: When ``True``, holding any one permission is sufficient.
            When ``False``, the principal must hold every permission in the set.

    Raises:
        PermissionDeniedError: If the check fails.
    """
    if any_:
        if principal.permissions.intersection(required):
            return
    elif required.issubset(principal.permissions):
        return
    _logger.warning(
        "event=rbac.permission_denied user_id=%s required_permission=%s timestamp=%s",
        principal.user_id,
        sorted(required),
        datetime.now(timezone.utc).isoformat(),
    )
    raise PermissionDeniedError("Not enough permissions")


def ensure_roles(principal: Principal, required: set[str]) -> None:
    """Assert that a principal holds at least one of the required roles or raise.

    Args:
        principal: The authenticated identity to check.
        required: The set of role names; membership in any one is sufficient.

    Raises:
        PermissionDeniedError: If the principal holds none of the required roles.
    """
    if required.intersection(principal.roles):
        return
    _logger.warning(
        "event=rbac.role_denied user_id=%s required_role=%s timestamp=%s",
        principal.user_id,
        sorted(required),
        datetime.now(timezone.utc).isoformat(),
    )
    raise PermissionDeniedError("Not enough roles")
