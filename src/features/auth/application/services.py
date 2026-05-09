"""Backward-compatible re-exports from the split auth service modules.

``AuthService`` and ``RBACService`` now live in their own modules; the
authorization helpers live in ``authorization.py``. Import directly from
those modules in new code. This shim keeps existing consumers working
without a flag-day migration.
"""

from src.features.auth.application.auth_service import (
    EMAIL_VERIFY_PURPOSE as EMAIL_VERIFY_PURPOSE,
)
from src.features.auth.application.auth_service import (
    PASSWORD_RESET_PURPOSE as PASSWORD_RESET_PURPOSE,
)
from src.features.auth.application.auth_service import (
    AuthService as AuthService,
)
from src.features.auth.application.authorization import (
    ensure_permissions as ensure_permissions,
)
from src.features.auth.application.authorization import (
    ensure_roles as ensure_roles,
)
from src.features.auth.application.rbac_service import RBACService as RBACService

__all__ = [
    "AuthService",
    "RBACService",
    "ensure_permissions",
    "ensure_roles",
    "PASSWORD_RESET_PURPOSE",
    "EMAIL_VERIFY_PURPOSE",
]
