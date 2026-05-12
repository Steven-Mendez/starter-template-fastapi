from __future__ import annotations

from dataclasses import dataclass

from src.features.authentication.application.cache import (
    InProcessPrincipalCache,
    PrincipalCachePort,
)
from src.features.authentication.application.errors import (
    AuthError,
    InactiveUserError,
    InvalidTokenError,
    StaleTokenError,
)
from src.features.authentication.application.jwt_tokens import AccessTokenService
from src.features.authentication.application.ports.outbound.auth_repository import (
    AuthRepositoryPort,
)
from src.platform.config.settings import AppSettings
from src.platform.shared.principal import Principal
from src.platform.shared.result import Err, Ok, Result


@dataclass(slots=True)
class ResolvePrincipalFromAccessToken:
    """Validate a JWT and resolve the current identity from the database."""

    _repository: AuthRepositoryPort
    _token_service: AccessTokenService
    _cache: PrincipalCachePort

    @classmethod
    def create(
        cls,
        repository: AuthRepositoryPort,
        token_service: AccessTokenService,
        settings: AppSettings,
        cache: PrincipalCachePort | None = None,
    ) -> "ResolvePrincipalFromAccessToken":
        resolved_cache = cache or InProcessPrincipalCache.create(
            ttl=settings.auth_principal_cache_ttl_seconds
        )
        return cls(
            _repository=repository,
            _token_service=token_service,
            _cache=resolved_cache,
        )

    def execute(self, token: str) -> Result[Principal, AuthError]:
        try:
            payload = self._token_service.decode(token)
        except InvalidTokenError as exc:
            return Err(exc)

        token_id = payload.token_id
        cached = self._cache.get(token_id)
        if cached is not None:
            return Ok(cached)

        principal = self._repository.get_principal(payload.subject)
        if principal is None:
            return Err(InvalidTokenError("Could not validate credentials"))
        if not principal.is_active:
            return Err(InactiveUserError("Inactive user"))
        if principal.authz_version != payload.authz_version:
            self._cache.pop(token_id)
            return Err(StaleTokenError("Stale authorization token"))

        self._cache.set(token_id, principal)
        return Ok(principal)
