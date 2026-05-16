"""Per-feature settings view used by the authentication composition root.

Holds only the values authentication actually consumes, derived from the
shared :class:`AppSettings`. The flat ``APP_AUTH_*`` env vars remain the
public contract — this struct is just a typed projection over them so the
composition root has a self-documenting dependency.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final, Literal

# Minimum length (in characters) for an HMAC-SHA JWT secret in production.
# 32 chars is the floor at which a single captured HS256 token is not
# brute-forceable on commodity GPU hardware.
_MIN_HS_JWT_SECRET_LEN: Final[int] = 32


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
    return_internal_tokens: bool
    auth_token_retention_days: int
    auth_token_purge_interval_minutes: int
    # Per-account lockout limiters. Composed AND-wise with the existing
    # per-(ip, email) limiter so a botnet of distinct IPs each under
    # the per-IP limit still trips the per-account budget. See
    # ``harden-rate-limiting``.
    per_account_login_max_attempts: int
    per_account_login_window_seconds: int
    per_account_reset_max_attempts: int
    per_account_reset_window_seconds: int
    per_account_verify_max_attempts: int
    per_account_verify_window_seconds: int

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
            return_internal_tokens=app.auth_return_internal_tokens,
            auth_token_retention_days=app.auth_token_retention_days,
            auth_token_purge_interval_minutes=app.auth_token_purge_interval_minutes,
            per_account_login_max_attempts=app.auth_per_account_login_max_attempts,
            per_account_login_window_seconds=(
                app.auth_per_account_login_window_seconds
            ),
            per_account_reset_max_attempts=app.auth_per_account_reset_max_attempts,
            per_account_reset_window_seconds=(
                app.auth_per_account_reset_window_seconds
            ),
            per_account_verify_max_attempts=app.auth_per_account_verify_max_attempts,
            per_account_verify_window_seconds=(
                app.auth_per_account_verify_window_seconds
            ),
        )

    def validate_production(self, errors: list[str]) -> None:
        """Append production-only validation errors for this feature."""
        if not self.jwt_secret_key:
            errors.append("APP_AUTH_JWT_SECRET_KEY must be set in production")
        elif (
            self.jwt_algorithm.startswith("HS")
            and len(self.jwt_secret_key) < _MIN_HS_JWT_SECRET_LEN
        ):
            # HMAC-SHA secrets are brute-forceable from a single captured
            # token when the key is short or low-entropy. 32 bytes is the
            # minimum for HS256 to resist offline brute-force on commodity
            # GPU hardware; HS384/HS512 should use proportionally longer
            # secrets but the validator pins the floor at 32 to keep the
            # error message actionable.
            errors.append(
                "APP_AUTH_JWT_SECRET_KEY must be at least 32 characters "
                "when APP_AUTH_JWT_ALGORITHM is an HMAC algorithm "
                f"(got {len(self.jwt_secret_key)} chars). Generate a "
                "strong secret with: openssl rand -hex 32"
            )
        if not self.jwt_issuer:
            errors.append("APP_AUTH_JWT_ISSUER must be set in production")
        if not self.jwt_audience:
            errors.append("APP_AUTH_JWT_AUDIENCE must be set in production")
        if not self.cookie_secure:
            errors.append("APP_AUTH_COOKIE_SECURE must be True in production")
        if self.cookie_samesite == "none":
            errors.append(
                "APP_AUTH_COOKIE_SAMESITE must be 'lax' or 'strict' in production; "
                "'none' allows third-party contexts to carry the refresh cookie "
                "and pair with cross-site POSTs that omit the Origin header"
            )
        if self.return_internal_tokens:
            errors.append("APP_AUTH_RETURN_INTERNAL_TOKENS must be False in production")
        if not self.redis_url:
            # Without Redis BOTH the rate limiter AND the principal
            # cache fall back to in-process state — every replica
            # maintains independent counters (effective rate limit x
            # replicas) and revoked principals keep acting on replicas
            # that did not see the cache invalidation. Both behaviors
            # are silent in single-replica dev environments and
            # production-critical at scale.
            errors.append(
                "APP_AUTH_REDIS_URL must be set in production: it is required "
                "by both the auth rate limiter (per-IP and per-account "
                "budgets must be shared across replicas; without Redis the "
                "effective limit is configured_limit * num_replicas) and "
                "the principal cache (revoked admins keep acting on "
                "replicas that did not see the in-process cache "
                "invalidation). Set APP_AUTH_REQUIRE_DISTRIBUTED_RATE_LIMIT=false "
                "only if the deployment is guaranteed to run as a single "
                "replica AND you accept the principal-cache staleness."
            )
