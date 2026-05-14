"""Per-feature settings view used by the authentication composition root.

Holds only the values authentication actually consumes, derived from the
shared :class:`AppSettings`. The flat ``APP_AUTH_*`` env vars remain the
public contract — this struct is just a typed projection over them so the
composition root has a self-documenting dependency.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


@dataclass(frozen=True, slots=True)
class AuthenticationSettings:
    """Subset of :class:`AppSettings` the authentication feature reads."""

    jwt_secret_key: str | None
    jwt_algorithm: str
    jwt_issuer: str | None
    jwt_audience: str | None
    jwt_leeway_seconds: int
    access_token_expire_minutes: int
    refresh_token_expire_days: int
    cookie_secure: bool
    cookie_samesite: Literal["lax", "strict", "none"]
    password_reset_token_expire_minutes: int
    email_verify_token_expire_minutes: int
    rate_limit_enabled: bool
    require_distributed_rate_limit: bool
    redis_url: str | None
    require_email_verification: bool
    seed_on_startup: bool
    bootstrap_super_admin_email: str | None
    bootstrap_super_admin_password: str | None
    bootstrap_promote_existing: bool
    default_user_role: str
    super_admin_role: str
    oauth_enabled: bool
    oauth_google_client_id: str | None
    oauth_google_client_secret: str | None
    oauth_google_redirect_uri: str | None
    return_internal_tokens: bool

    @classmethod
    def from_app_settings(cls, app: Any) -> AuthenticationSettings:
        """Project the flat ``APP_AUTH_*`` fields of an AppSettings-like
        object into this feature's structured view. ``app`` is duck-typed
        so per-feature settings stay decoupled from :class:`AppSettings`."""
        return cls(
            jwt_secret_key=app.auth_jwt_secret_key,
            jwt_algorithm=app.auth_jwt_algorithm,
            jwt_issuer=app.auth_jwt_issuer,
            jwt_audience=app.auth_jwt_audience,
            jwt_leeway_seconds=app.auth_jwt_leeway_seconds,
            access_token_expire_minutes=app.auth_access_token_expire_minutes,
            refresh_token_expire_days=app.auth_refresh_token_expire_days,
            cookie_secure=app.auth_cookie_secure,
            cookie_samesite=app.auth_cookie_samesite,
            password_reset_token_expire_minutes=(
                app.auth_password_reset_token_expire_minutes
            ),
            email_verify_token_expire_minutes=(
                app.auth_email_verify_token_expire_minutes
            ),
            rate_limit_enabled=app.auth_rate_limit_enabled,
            require_distributed_rate_limit=app.auth_require_distributed_rate_limit,
            redis_url=app.auth_redis_url,
            require_email_verification=app.auth_require_email_verification,
            seed_on_startup=app.auth_seed_on_startup,
            bootstrap_super_admin_email=app.auth_bootstrap_super_admin_email,
            bootstrap_super_admin_password=app.auth_bootstrap_super_admin_password,
            bootstrap_promote_existing=app.auth_bootstrap_promote_existing,
            default_user_role=app.auth_default_user_role,
            super_admin_role=app.auth_super_admin_role,
            oauth_enabled=app.auth_oauth_enabled,
            oauth_google_client_id=app.auth_oauth_google_client_id,
            oauth_google_client_secret=app.auth_oauth_google_client_secret,
            oauth_google_redirect_uri=app.auth_oauth_google_redirect_uri,
            return_internal_tokens=app.auth_return_internal_tokens,
        )

    def validate_production(self, errors: list[str]) -> None:
        """Append production-only validation errors for this feature."""
        if not self.jwt_secret_key:
            errors.append("APP_AUTH_JWT_SECRET_KEY must be set in production")
        if not self.jwt_issuer:
            errors.append("APP_AUTH_JWT_ISSUER must be set in production")
        if not self.jwt_audience:
            errors.append("APP_AUTH_JWT_AUDIENCE must be set in production")
        if not self.cookie_secure:
            errors.append("APP_AUTH_COOKIE_SECURE must be True in production")
        if self.return_internal_tokens:
            errors.append("APP_AUTH_RETURN_INTERNAL_TOKENS must be False in production")
        if self.require_distributed_rate_limit and not self.redis_url:
            errors.append(
                "APP_AUTH_REDIS_URL must be set in production when "
                "APP_AUTH_REQUIRE_DISTRIBUTED_RATE_LIMIT is true; "
                "set APP_AUTH_REQUIRE_DISTRIBUTED_RATE_LIMIT=false only if "
                "the deployment is guaranteed to run as a single replica"
            )
