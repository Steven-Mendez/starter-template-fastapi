"""Unit tests for :class:`AppSettings` defaults, env overrides, and validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app_platform.config.settings import AppSettings, get_settings
from app_platform.config.sub_settings import DatabaseSettings

pytestmark = pytest.mark.unit

_VALID_PROD_ENV = {
    "APP_ENVIRONMENT": "production",
    "APP_ENABLE_DOCS": "false",
    "APP_AUTH_JWT_SECRET_KEY": "a-secret-at-least-32-chars-long!!",
    "APP_AUTH_JWT_ISSUER": "https://issuer.example.com",
    "APP_AUTH_JWT_AUDIENCE": "starter-template-fastapi",
    "APP_CORS_ORIGINS": '["https://example.com"]',
    "APP_TRUSTED_HOSTS": '["example.com"]',
    "APP_TRUSTED_PROXY_IPS": '["10.0.0.0/8"]',
    "APP_APP_PUBLIC_URL": "https://example.com",
    "APP_AUTH_COOKIE_SECURE": "true",
    "APP_AUTH_REDIS_URL": "redis://localhost:6379/0",
    "APP_EMAIL_BACKEND": "resend",
    "APP_EMAIL_RESEND_API_KEY": "re_test_key",
    "APP_EMAIL_FROM": "no-reply@example.com",
    "APP_JOBS_BACKEND": "arq",
    "APP_JOBS_REDIS_URL": "redis://localhost:6379/0",
    "APP_OUTBOX_ENABLED": "true",
}


def test_defaults_in_development(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in [
        "APP_ENVIRONMENT",
        "APP_ENABLE_DOCS",
        "APP_CORS_ORIGINS",
        "APP_TRUSTED_HOSTS",
    ]:
        monkeypatch.delenv(key, raising=False)
    s = AppSettings(_env_file=None)  # type: ignore[call-arg]
    assert s.environment == "development"
    assert s.enable_docs is True
    assert s.cors_origins == ["*"]


def test_env_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    for k, v in _VALID_PROD_ENV.items():
        monkeypatch.setenv(k, v)
    s = AppSettings(_env_file=None)  # type: ignore[call-arg]
    assert s.environment == "production"
    assert s.enable_docs is False
    assert s.auth_jwt_secret_key == "a-secret-at-least-32-chars-long!!"
    assert s.auth_cookie_secure is True


def test_invalid_environment_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENVIRONMENT", "staging")
    with pytest.raises(ValidationError):
        AppSettings(_env_file=None)  # type: ignore[call-arg]


def test_cors_origins_parsed_as_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_CORS_ORIGINS", '["https://a.example", "https://b.example"]')
    s = AppSettings(_env_file=None)  # type: ignore[call-arg]
    assert s.cors_origins == ["https://a.example", "https://b.example"]


def test_default_database_pool_sized_for_anyio_threadpool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The default pool ceiling must exceed AnyIO's ~40-worker threadpool.

    See ``docs/operations.md`` Pool sizing section for the formula.
    """
    for key in [
        "APP_DB_POOL_SIZE",
        "APP_DB_MAX_OVERFLOW",
    ]:
        monkeypatch.delenv(key, raising=False)
    settings = AppSettings(_env_file=None)  # type: ignore[call-arg]
    db = DatabaseSettings.from_app_settings(settings)
    assert db.pool_size == 20
    assert db.max_overflow == 30
    # Sanity: total ceiling exceeds AnyIO threadpool defaults.
    assert db.pool_size + db.max_overflow >= 40


def test_get_settings_caches(monkeypatch: pytest.MonkeyPatch) -> None:
    get_settings.cache_clear()
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2
    get_settings.cache_clear()


def test_production_requires_jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    for k, v in _VALID_PROD_ENV.items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("APP_AUTH_JWT_SECRET_KEY", raising=False)
    with pytest.raises(ValidationError, match="APP_AUTH_JWT_SECRET_KEY"):
        AppSettings(_env_file=None)  # type: ignore[call-arg]


def test_production_requires_jwt_issuer(monkeypatch: pytest.MonkeyPatch) -> None:
    for k, v in _VALID_PROD_ENV.items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("APP_AUTH_JWT_ISSUER", raising=False)
    with pytest.raises(ValidationError, match="APP_AUTH_JWT_ISSUER"):
        AppSettings(_env_file=None)  # type: ignore[call-arg]


def test_production_requires_jwt_audience(monkeypatch: pytest.MonkeyPatch) -> None:
    for k, v in _VALID_PROD_ENV.items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("APP_AUTH_JWT_AUDIENCE", raising=False)
    with pytest.raises(ValidationError, match="APP_AUTH_JWT_AUDIENCE"):
        AppSettings(_env_file=None)  # type: ignore[call-arg]


def test_production_rejects_wildcard_cors(monkeypatch: pytest.MonkeyPatch) -> None:
    for k, v in _VALID_PROD_ENV.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("APP_CORS_ORIGINS", '["*"]')
    with pytest.raises(ValidationError, match="APP_CORS_ORIGINS"):
        AppSettings(_env_file=None)  # type: ignore[call-arg]


def test_production_rejects_insecure_cookie(monkeypatch: pytest.MonkeyPatch) -> None:
    for k, v in _VALID_PROD_ENV.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("APP_AUTH_COOKIE_SECURE", "false")
    with pytest.raises(ValidationError, match="APP_AUTH_COOKIE_SECURE"):
        AppSettings(_env_file=None)  # type: ignore[call-arg]


def test_production_rejects_samesite_none(monkeypatch: pytest.MonkeyPatch) -> None:
    """``APP_AUTH_COOKIE_SAMESITE=none`` is refused in production.

    SameSite=none allows third-party contexts to carry the refresh
    cookie, which pairs with cross-site POSTs that omit the ``Origin``
    header to bypass the cookie-origin check. The production validator
    refuses ``none`` so the deployment must pick ``lax`` or ``strict``.
    """
    for k, v in _VALID_PROD_ENV.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("APP_AUTH_COOKIE_SAMESITE", "none")
    with pytest.raises(ValidationError, match="APP_AUTH_COOKIE_SAMESITE"):
        AppSettings(_env_file=None)  # type: ignore[call-arg]


@pytest.mark.parametrize("value", ["lax", "strict"])
def test_production_accepts_samesite_lax_or_strict(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    """``lax`` and ``strict`` remain valid in production — only ``none`` is refused."""
    for k, v in _VALID_PROD_ENV.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("APP_AUTH_COOKIE_SAMESITE", value)
    settings = AppSettings(_env_file=None)  # type: ignore[call-arg]
    assert settings.auth_cookie_samesite == value


def test_production_rejects_enabled_docs(monkeypatch: pytest.MonkeyPatch) -> None:
    for k, v in _VALID_PROD_ENV.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("APP_ENABLE_DOCS", "true")
    with pytest.raises(ValidationError, match="APP_ENABLE_DOCS"):
        AppSettings(_env_file=None)  # type: ignore[call-arg]


def test_invalid_jwt_algorithm_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_AUTH_JWT_ALGORITHM", "none")
    with pytest.raises(ValidationError, match="APP_AUTH_JWT_ALGORITHM"):
        AppSettings(_env_file=None)  # type: ignore[call-arg]


def test_production_rejects_raw_wildcard_cors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for k, v in _VALID_PROD_ENV.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("APP_CORS_ORIGINS", '["*"]')
    with pytest.raises(ValidationError, match="APP_CORS_ORIGINS"):
        AppSettings(_env_file=None)  # type: ignore[call-arg]


def test_production_rejects_console_email(monkeypatch: pytest.MonkeyPatch) -> None:
    for k, v in _VALID_PROD_ENV.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("APP_EMAIL_BACKEND", "console")
    with pytest.raises(ValidationError, match="APP_EMAIL_BACKEND"):
        AppSettings(_env_file=None)  # type: ignore[call-arg]


def test_production_rejects_return_internal_tokens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for k, v in _VALID_PROD_ENV.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("APP_AUTH_RETURN_INTERNAL_TOKENS", "true")
    with pytest.raises(ValidationError, match="APP_AUTH_RETURN_INTERNAL_TOKENS"):
        AppSettings(_env_file=None)  # type: ignore[call-arg]


def test_production_rejects_in_process_jobs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for k, v in _VALID_PROD_ENV.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("APP_JOBS_BACKEND", "in_process")
    monkeypatch.delenv("APP_JOBS_REDIS_URL", raising=False)
    with pytest.raises(ValidationError, match="APP_JOBS_BACKEND"):
        AppSettings(_env_file=None)  # type: ignore[call-arg]


def test_arq_backend_requires_redis_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_JOBS_BACKEND", "arq")
    monkeypatch.delenv("APP_JOBS_REDIS_URL", raising=False)
    monkeypatch.delenv("APP_AUTH_REDIS_URL", raising=False)
    with pytest.raises(ValidationError, match="APP_JOBS_REDIS_URL"):
        AppSettings(_env_file=None)  # type: ignore[call-arg]


def test_resend_backend_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_EMAIL_BACKEND", "resend")
    monkeypatch.setenv("APP_EMAIL_FROM", "no-reply@example.com")
    monkeypatch.delenv("APP_EMAIL_RESEND_API_KEY", raising=False)
    with pytest.raises(ValidationError, match="APP_EMAIL_RESEND_API_KEY"):
        AppSettings(_env_file=None)  # type: ignore[call-arg]


def test_resend_backend_requires_from(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_EMAIL_BACKEND", "resend")
    monkeypatch.setenv("APP_EMAIL_RESEND_API_KEY", "re_test_key")
    monkeypatch.delenv("APP_EMAIL_FROM", raising=False)
    with pytest.raises(ValidationError, match="APP_EMAIL_FROM"):
        AppSettings(_env_file=None)  # type: ignore[call-arg]


def test_production_accepts_resend_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    for k, v in _VALID_PROD_ENV.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("APP_EMAIL_BACKEND", "resend")
    monkeypatch.setenv("APP_EMAIL_RESEND_API_KEY", "re_test_key")
    # Resend only needs FROM + key — construct should succeed without raising.
    settings = AppSettings(_env_file=None)  # type: ignore[call-arg]
    assert settings.email_backend == "resend"


def test_production_rejects_disabled_outbox(monkeypatch: pytest.MonkeyPatch) -> None:
    for k, v in _VALID_PROD_ENV.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("APP_OUTBOX_ENABLED", "false")
    with pytest.raises(ValidationError, match="APP_OUTBOX_ENABLED"):
        AppSettings(_env_file=None)  # type: ignore[call-arg]


def test_production_accepts_enabled_outbox(monkeypatch: pytest.MonkeyPatch) -> None:
    for k, v in _VALID_PROD_ENV.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("APP_OUTBOX_ENABLED", "true")
    settings = AppSettings(_env_file=None)  # type: ignore[call-arg]
    assert settings.outbox_enabled is True


def test_outbox_relay_interval_must_be_positive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_OUTBOX_RELAY_INTERVAL_SECONDS", "0")
    with pytest.raises(ValidationError, match="APP_OUTBOX_RELAY_INTERVAL_SECONDS"):
        AppSettings(_env_file=None)  # type: ignore[call-arg]


def test_outbox_claim_batch_size_must_be_positive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_OUTBOX_CLAIM_BATCH_SIZE", "0")
    with pytest.raises(ValidationError, match="APP_OUTBOX_CLAIM_BATCH_SIZE"):
        AppSettings(_env_file=None)  # type: ignore[call-arg]


def test_outbox_max_attempts_must_be_positive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_OUTBOX_MAX_ATTEMPTS", "0")
    with pytest.raises(ValidationError, match="APP_OUTBOX_MAX_ATTEMPTS"):
        AppSettings(_env_file=None)  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# harden-rate-limiting (tasks 5.4, 5.5): the production validator MUST refuse
# unsafe defaults around the rate limiter and the principal cache. Both gaps
# are silent in development (single-machine, no proxy) and trivially
# bypassable in production until the validator refuses to boot.
# ---------------------------------------------------------------------------


def test_production_rejects_empty_trusted_proxy_ips(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Task 5.4: empty ``APP_TRUSTED_PROXY_IPS`` is refused in production.

    Without trusted proxies the rate limiter sees the load balancer's
    IP for every request — one attacker exhausts the bucket for every
    legitimate client. Pin the refusal so a future settings refactor
    cannot reintroduce the silent default.
    """
    for k, v in _VALID_PROD_ENV.items():
        monkeypatch.setenv(k, v)
    # Pydantic treats an empty JSON list as a literal empty list, which
    # is what the dev default looks like — the worst-case configuration
    # we want to refuse.
    monkeypatch.setenv("APP_TRUSTED_PROXY_IPS", "[]")
    with pytest.raises(ValidationError, match="APP_TRUSTED_PROXY_IPS"):
        AppSettings(_env_file=None)  # type: ignore[call-arg]


def test_production_accepts_non_empty_trusted_proxy_ips(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A non-empty CIDR list satisfies the validator.

    Sanity check that the validator does NOT also reject a correct
    configuration — without this the previous test could pass on a
    validator that always raises.
    """
    for k, v in _VALID_PROD_ENV.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("APP_TRUSTED_PROXY_IPS", '["10.0.0.0/8", "192.168.0.0/16"]')
    settings = AppSettings(_env_file=None)  # type: ignore[call-arg]
    assert settings.trusted_proxy_ips == ["10.0.0.0/8", "192.168.0.0/16"]


def test_production_requires_redis_for_principal_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Task 5.5: missing ``APP_AUTH_REDIS_URL`` is refused in production.

    The error message MUST mention BOTH the rate limiter AND the
    principal cache — the two gaps are independent and an operator
    reading the message needs to understand which fix is being asked
    for. A message that only mentions one half hides the other gap.
    """
    for k, v in _VALID_PROD_ENV.items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("APP_AUTH_REDIS_URL", raising=False)

    with pytest.raises(ValidationError) as exc_info:
        AppSettings(_env_file=None)  # type: ignore[call-arg]

    message = str(exc_info.value)
    # The validator points at the setting that needs flipping.
    assert "APP_AUTH_REDIS_URL" in message
    # Per task 5.5: the message MUST cover both the rate limiter AND the
    # principal cache so an operator sees both subsystems on one line.
    assert "rate limiter" in message.lower(), (
        f"validator error must mention the rate limiter; got: {message}"
    )
    assert "principal cache" in message.lower(), (
        f"validator error must mention the principal cache; got: {message}"
    )


# ---------------------------------------------------------------------------
# strengthen-production-validators (tasks 5.1-5.3): cover three existing
# refusals that previously had no test. A silent regression on any of these
# would let a production deploy boot with an unsafe default.
# ---------------------------------------------------------------------------


def test_production_rejects_rbac_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Task 5.1: ``APP_AUTH_RBAC_ENABLED=false`` is refused in production.

    Disabling RBAC removes every authorization check; the validator must
    fail loudly so a flipped flag does not silently ship.
    """
    for k, v in _VALID_PROD_ENV.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("APP_AUTH_RBAC_ENABLED", "false")
    with pytest.raises(ValidationError, match="APP_AUTH_RBAC_ENABLED"):
        AppSettings(_env_file=None)  # type: ignore[call-arg]


def test_production_rejects_local_storage_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Task 5.2: ``APP_STORAGE_BACKEND=local`` with storage ENABLED is refused.

    Local-disk storage is per-pod state; multi-replica deploys would
    silently lose blobs on the wrong node. The validator only refuses
    when storage is actually wired (``storage_enabled=True``), so
    deployments that do not use file storage are not forced to set up S3.
    """
    for k, v in _VALID_PROD_ENV.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("APP_STORAGE_ENABLED", "true")
    monkeypatch.setenv("APP_STORAGE_BACKEND", "local")
    with pytest.raises(ValidationError, match="APP_STORAGE_BACKEND"):
        AppSettings(_env_file=None)  # type: ignore[call-arg]


def test_production_rejects_distributed_rate_limit_without_redis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Task 5.3: ``APP_AUTH_REQUIRE_DISTRIBUTED_RATE_LIMIT=true`` without
    ``APP_AUTH_REDIS_URL`` is refused in production.

    This overlaps with the harden-rate-limiting Redis-required test, but
    pinning the specific (require_distributed=true, no Redis) combination
    catches a regression that flips Redis off while leaving the
    distributed-required flag on.
    """
    for k, v in _VALID_PROD_ENV.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("APP_AUTH_REQUIRE_DISTRIBUTED_RATE_LIMIT", "true")
    monkeypatch.delenv("APP_AUTH_REDIS_URL", raising=False)
    with pytest.raises(ValidationError, match="APP_AUTH_REDIS_URL"):
        AppSettings(_env_file=None)  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# strengthen-production-validators (tasks 6.1-6.5): four new refusals close
# previously-unenforced gaps — short HS JWT secrets, wildcard trusted hosts,
# unset/non-HTTPS ``app_public_url``, and ``app_public_url`` host not present
# in the CORS origin list.
# ---------------------------------------------------------------------------


def test_production_rejects_short_jwt_hs_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Task 6.1: short HS-algorithm JWT secrets are refused in production.

    A 32-character floor blocks brute-force from a single captured HS256
    token. The error message MUST point at ``APP_AUTH_JWT_SECRET_KEY`` so
    the operator knows which knob to fix.
    """
    for k, v in _VALID_PROD_ENV.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("APP_AUTH_JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("APP_AUTH_JWT_SECRET_KEY", "short")
    with pytest.raises(ValidationError, match="APP_AUTH_JWT_SECRET_KEY"):
        AppSettings(_env_file=None)  # type: ignore[call-arg]


def test_production_accepts_short_secret_with_non_hs_algorithm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Task 6.2: the length floor only applies to HS-family algorithms.

    For asymmetric algorithms (RS256, etc.) the secret_key field is not
    used as an HMAC key, so the length check should not fire. Other
    checks may still fail for an RS256 deploy, but this particular check
    must not raise on a short secret when the algorithm is non-HS.
    """
    for k, v in _VALID_PROD_ENV.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("APP_AUTH_JWT_ALGORITHM", "RS256")
    monkeypatch.setenv("APP_AUTH_JWT_SECRET_KEY", "short")

    # Either construction succeeds OR it fails for some other reason —
    # but the HS-length check must NOT be the source of the failure.
    try:
        AppSettings(_env_file=None)  # type: ignore[call-arg]
    except ValidationError as exc:
        message = str(exc)
        assert "at least 32 characters" not in message, (
            f"HS-length check must not fire for RS256 algorithm; got error: {message}"
        )
        assert "HMAC algorithm" not in message, (
            f"HS-length check must not fire for RS256 algorithm; got error: {message}"
        )


def test_production_rejects_wildcard_trusted_hosts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Task 6.3: ``APP_TRUSTED_HOSTS=['*']`` is refused in production.

    A wildcard turns ``TrustedHostMiddleware`` into a no-op and removes
    Host-header spoofing defence. Production must list the explicit
    public hostnames.
    """
    for k, v in _VALID_PROD_ENV.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("APP_TRUSTED_HOSTS", '["*"]')
    with pytest.raises(ValidationError, match="APP_TRUSTED_HOSTS"):
        AppSettings(_env_file=None)  # type: ignore[call-arg]


def test_production_rejects_partial_wildcard_trusted_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Task 6.3: any wildcard pattern (e.g. ``*.example.com``) is refused.

    Starlette accepts ``*.example.com`` as a subdomain wildcard; the
    validator refuses any entry containing a wildcard so the deployment
    must name hosts explicitly.
    """
    for k, v in _VALID_PROD_ENV.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("APP_TRUSTED_HOSTS", '["foo*.example.com"]')
    with pytest.raises(ValidationError, match="APP_TRUSTED_HOSTS"):
        AppSettings(_env_file=None)  # type: ignore[call-arg]


def test_production_rejects_unset_or_non_https_app_public_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Task 6.4: ``APP_APP_PUBLIC_URL`` MUST be set AND use HTTPS in production.

    The URL is interpolated verbatim into password-reset and email-verify
    links; a misconfigured value silently directs reset tokens off-platform.
    Both empty and non-HTTPS values must be refused.

    Note: the pydantic-settings env prefix is ``APP_``, so the field
    ``app_public_url`` reads from ``APP_APP_PUBLIC_URL`` (not ``APP_PUBLIC_URL``).
    """
    # Form 1: empty value — set to the empty string so the env var is
    # observed but no URL is supplied.
    for k, v in _VALID_PROD_ENV.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("APP_APP_PUBLIC_URL", "")
    with pytest.raises(ValidationError, match="APP_APP_PUBLIC_URL"):
        AppSettings(_env_file=None)  # type: ignore[call-arg]

    # Form 2: non-HTTPS scheme — http:// must be refused even when host
    # matches the CORS origin list.
    for k, v in _VALID_PROD_ENV.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("APP_APP_PUBLIC_URL", "http://example.com")
    with pytest.raises(ValidationError, match="APP_APP_PUBLIC_URL") as exc_info:
        AppSettings(_env_file=None)  # type: ignore[call-arg]
    assert "https" in str(exc_info.value).lower(), (
        f"non-HTTPS refusal must reference the https scheme; got: {exc_info.value}"
    )


def test_production_rejects_app_public_url_host_not_in_cors_origins(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Task 6.5: the public URL host MUST appear in ``APP_CORS_ORIGINS``.

    The CORS origin list is the canonical declaration of "we trust this
    surface". Pinning the public URL's host to that set ensures
    password-reset / email-verify links never leave the trusted surface
    — even when the operator forgets to mirror the values.
    """
    for k, v in _VALID_PROD_ENV.items():
        monkeypatch.setenv(k, v)
    # CORS origins lists ``https://example.com``, public URL points at a
    # different host so the membership check fails.
    monkeypatch.setenv("APP_CORS_ORIGINS", '["https://example.com"]')
    monkeypatch.setenv("APP_APP_PUBLIC_URL", "https://attacker.example.org")
    monkeypatch.setenv("APP_TRUSTED_HOSTS", '["example.com", "attacker.example.org"]')

    with pytest.raises(ValidationError, match="APP_APP_PUBLIC_URL") as exc_info:
        AppSettings(_env_file=None)  # type: ignore[call-arg]
    message = str(exc_info.value)
    assert "APP_CORS_ORIGINS" in message, (
        "host-mismatch error must mention APP_CORS_ORIGINS so the "
        f"operator knows where to add the surface; got: {message}"
    )
