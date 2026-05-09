from __future__ import annotations

from dataclasses import dataclass

from src.features.auth.application.cache import PrincipalCachePort
from src.features.auth.application.errors import (
    AuthError,
    DuplicateEmailError,
    NotFoundError,
)
from src.features.auth.application.normalization import normalize_email
from src.features.auth.application.ports.outbound.auth_repository import (
    AuthRepositoryPort,
)
from src.features.auth.application.use_cases.auth.register_user import RegisterUser
from src.features.auth.application.use_cases.rbac.seed_initial_data import (
    SeedInitialData,
)
from src.features.auth.domain.models import User
from src.platform.shared.result import Err, Ok, Result


@dataclass(slots=True)
class BootstrapSuperAdmin:
    """Seed data and ensure the given account has the super_admin role."""

    _repository: AuthRepositoryPort
    _seed: SeedInitialData
    _register_user: RegisterUser
    _cache: PrincipalCachePort | None = None

    def execute(
        self,
        *,
        email: str,
        password: str,
    ) -> Result[User, AuthError]:
        match self._seed.execute():
            case Err() as err:
                return err

        normalized_email = normalize_email(email)
        user = self._repository.get_user_by_email(normalized_email)
        if user is None:
            reg_result = self._register_user.execute(
                email=normalized_email, password=password
            )
            match reg_result:
                case Ok(value=created):
                    user = created
                case Err(error=exc):
                    if isinstance(exc, DuplicateEmailError):
                        # Two replicas racing at startup; retry the lookup.
                        user = self._repository.get_user_by_email(normalized_email)
                        if user is None:
                            return Err(exc)
                    else:
                        return Err(exc)

        role = self._repository.get_role_by_name("super_admin")
        if role is None:
            return Err(NotFoundError("super_admin role not found"))

        self._repository.assign_user_role(user.id, role.id)
        if self._cache is not None:
            self._cache.invalidate_user(user.id)
        self._repository.record_audit_event(
            event_type="rbac.super_admin_bootstrapped",
            user_id=user.id,
            metadata={"role_id": str(role.id)},
        )
        refreshed = self._repository.get_user_by_id(user.id)
        if refreshed is None:
            return Err(NotFoundError("User not found"))
        return Ok(refreshed)
