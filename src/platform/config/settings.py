"""Runtime configuration loaded from environment variables and .env."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Strongly-typed view over runtime configuration.

    Values are populated from environment variables prefixed with ``APP_``
    and from a ``.env`` file when present, with environment variables
    taking precedence. Unknown keys are ignored so individual deployments
    can carry extra variables without breaking validation.

    Auth-related fields are grouped together at the bottom of the class
    and most have safe defaults so the application boots in development
    without any secrets configured. ``auth_jwt_secret_key`` is the one
    field that must be set in any deployment that issues real tokens.
    """

    model_config = SettingsConfigDict(
        env_prefix="APP_",
        env_file=".env",
        extra="ignore",
    )

    environment: Literal["development", "test", "production"] = "development"
    enable_docs: bool = True
    cors_origins: list[str] = ["*"]
    trusted_hosts: list[str] = ["*"]
    log_level: str = "INFO"
    postgresql_dsn: str = "postgresql+psycopg://postgres:postgres@localhost:5432/kanban"
    health_persistence_backend: str = "postgresql"
    write_api_key: str | None = None
    auth_jwt_secret_key: str | None = None
    auth_jwt_algorithm: str = "HS256"
    auth_jwt_issuer: str | None = None
    auth_jwt_audience: str | None = None
    auth_access_token_expire_minutes: int = 15
    auth_refresh_token_expire_days: int = 30
    auth_cookie_secure: bool = False
    auth_cookie_samesite: Literal["lax", "strict", "none"] = "strict"
    auth_password_reset_token_expire_minutes: int = 30
    auth_email_verify_token_expire_minutes: int = 1440
    auth_rate_limit_enabled: bool = True
    auth_rbac_enabled: bool = True
    auth_seed_on_startup: bool = False
    auth_bootstrap_super_admin_email: str | None = None
    auth_bootstrap_super_admin_password: str | None = None
    auth_default_user_role: str = "user"
    auth_super_admin_role: str = "super_admin"
    auth_oauth_enabled: bool = False
    auth_oauth_google_client_id: str | None = None
    auth_oauth_google_client_secret: str | None = None
    auth_oauth_google_redirect_uri: str | None = None
    # MUST stay False in production: enabling it surfaces single-use
    # password-reset / email-verify tokens in API responses, which is
    # only acceptable for local development and e2e tests.
    auth_return_internal_tokens: bool = False
    # When set, the auth rate limiter uses Redis so the limit applies
    # globally across all replicas; otherwise an in-process limiter is used.
    auth_redis_url: str | None = None

    @model_validator(mode="after")
    def _validate_production_settings(self) -> "AppSettings":
        """Refuse to start in production if critical security settings are missing."""
        if self.environment != "production":
            return self
        errors: list[str] = []
        if not self.auth_jwt_secret_key:
            errors.append("APP_AUTH_JWT_SECRET_KEY must be set in production")
        if self.cors_origins == ["*"] or "*" in self.cors_origins:
            errors.append(
                "APP_CORS_ORIGINS must not be ['*'] in production; "
                "provide explicit allowed origins"
            )
        if not self.auth_cookie_secure:
            errors.append("APP_AUTH_COOKIE_SECURE must be True in production")
        if self.enable_docs:
            errors.append("APP_ENABLE_DOCS must be False in production")
        if errors:
            raise ValueError(
                "Production configuration errors:\n"
                + "\n".join(f"  - {e}" for e in errors)
            )
        return self


@lru_cache
def get_settings() -> AppSettings:
    """Return a process-wide cached :class:`AppSettings` instance.

    Caching avoids re-parsing the environment on every request and gives
    the settings object pseudo-singleton semantics, while ``lru_cache``
    keeps the function easy to reset in tests via ``cache_clear()``.
    """
    return AppSettings()
