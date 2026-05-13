"""Per-feature settings view used by the authorization composition root.

The authorization feature owns two runtime knobs today: the RBAC enable
flag and the principal cache TTL. They live under ``APP_AUTH_*`` env-var
names for backwards compatibility (the rename predates the
authentication/authorization split) and are re-exposed here as a typed
projection.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class AuthorizationSettings:
    """Subset of :class:`AppSettings` the authorization feature reads."""

    rbac_enabled: bool
    principal_cache_ttl_seconds: int

    @classmethod
    def from_app_settings(cls, app: Any) -> AuthorizationSettings:
        return cls(
            rbac_enabled=app.auth_rbac_enabled,
            principal_cache_ttl_seconds=app.auth_principal_cache_ttl_seconds,
        )

    def validate_production(self, errors: list[str]) -> None:
        if not self.rbac_enabled:
            errors.append("APP_AUTH_RBAC_ENABLED must be True in production")
