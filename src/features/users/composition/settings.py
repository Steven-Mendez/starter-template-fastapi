"""Per-feature settings view used by the users composition root.

The users feature currently has very little dedicated configuration; the
two settings it exposes are the default role assigned at registration
and the marker role used by the bootstrap admin flow. Both live under
``APP_AUTH_*`` env-var names today for backwards compatibility and are
re-exposed here as a typed projection.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class UsersSettings:
    """Subset of :class:`AppSettings` the users feature reads."""

    default_user_role: str
    super_admin_role: str
    require_email_verification: bool

    @classmethod
    def from_app_settings(cls, app: Any) -> UsersSettings:
        return cls(
            default_user_role=app.auth_default_user_role,
            super_admin_role=app.auth_super_admin_role,
            require_email_verification=app.auth_require_email_verification,
        )

    def validate_production(self, errors: list[str]) -> None:  # noqa: ARG002
        """No additional production-only constraints today."""
        return
