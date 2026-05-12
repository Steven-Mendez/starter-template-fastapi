from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from src.features.authentication.application.cache import PrincipalCachePort
from src.features.authentication.application.crypto import hash_token
from src.features.authentication.application.errors import AuthError
from src.features.authentication.application.ports.outbound.auth_repository import (
    AuthRepositoryPort,
)
from src.platform.shared.result import Ok, Result


@dataclass(slots=True)
class LogoutUser:
    """Revoke the current session's refresh token."""

    _repository: AuthRepositoryPort
    _cache: PrincipalCachePort | None = None

    def execute(
        self,
        refresh_token: str | None,
    ) -> Result[None, AuthError]:
        if not refresh_token:
            return Ok(None)
        record = self._repository.get_refresh_token_by_hash(hash_token(refresh_token))
        if record is not None and record.revoked_at is None:
            self._repository.revoke_refresh_token(record.id)
        return Ok(None)


@dataclass(slots=True)
class LogoutAllSessions:
    """Revoke all active sessions for a user simultaneously."""

    _repository: AuthRepositoryPort
    _cache: PrincipalCachePort | None = None

    def execute(
        self,
        *,
        user_id: UUID,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> Result[None, AuthError]:
        self._repository.revoke_user_refresh_tokens(user_id)
        if self._cache is not None:
            self._cache.invalidate_user(user_id)
        self._repository.record_audit_event(
            event_type="auth.logout_all",
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return Ok(None)
