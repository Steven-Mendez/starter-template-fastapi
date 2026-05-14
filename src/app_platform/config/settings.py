"""Runtime configuration loaded from environment variables and .env.

:class:`AppSettings` is the single env-loading boundary; it holds the
flat ``APP_*`` fields that pydantic-settings populates from the
environment. Per-feature and platform sub-settings classes
(:class:`AuthenticationSettings`, :class:`EmailSettings`,
:class:`DatabaseSettings`, …) are typed projections built from this
class via their ``from_app_settings(app)`` classmethods. They live in
each feature's ``composition/settings.py`` (and, for cross-cutting
platform knobs, in :mod:`app_platform.config.sub_settings`), so a
feature owns its config — including its production-validation method
— alongside the rest of its code.

The aggregation pattern: each sub-settings class defines a
``validate_production(self, errors: list[str]) -> None`` method.
:class:`AppSettings` constructs each sub-settings projection during
``_validate_production_settings`` and calls those methods, aggregating
all error messages into a single :class:`ValueError`.

Why the flat fields remain: ``APP_*`` env vars are the public contract.
Every existing consumer reads ``settings.<flat_attr>`` and continues to
work. New code that wants the structured view writes
``settings.email`` or ``EmailSettings.from_app_settings(settings)``.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app_platform.config.sub_settings import (
    ApiSettings,
    DatabaseSettings,
    ObservabilitySettings,
)

JWT_ALGORITHM_WHITELIST = {"HS256", "RS256"}
MAX_JWT_LEEWAY_SECONDS = 60


class AppSettings(BaseSettings):
    """Strongly-typed view over runtime configuration.

    Values are populated from environment variables prefixed with ``APP_``
    and from a ``.env`` file when present, with environment variables
    taking precedence. Unknown keys are ignored so individual deployments
    can carry extra variables without breaking validation.

    Flat ``APP_*`` fields stay the public contract. Structured per-feature
    views (``settings.email``, ``settings.jobs``, …) are computed on
    demand from those fields and own their own production-validation
    methods, which ``_validate_production_settings`` aggregates.
    """

    model_config = SettingsConfigDict(
        env_prefix="APP_",
        env_file=".env",
        extra="ignore",
    )

    environment: Literal["development", "test", "production"] = "development"
    enable_docs: bool = True
    # Public-facing URL the application is reachable at — used to build the
    # links embedded in transactional emails (password reset, email verify).
    # Trailing slashes are stripped at use time.
    app_public_url: str = "http://localhost:8000"
    # Short human-friendly product name used in subject lines and signatures.
    app_display_name: str = "Starter"
    cors_origins: list[str] = ["*"]
    trusted_hosts: list[str] = ["*"]
    log_level: str = "INFO"
    postgresql_dsn: str = (
        "postgresql+psycopg://postgres:postgres@localhost:5432/starter"
    )
    health_persistence_backend: str = "postgresql"
    # Database connection-pool tuning. ``pool_recycle`` defends against
    # idle-cutting load balancers (RDS, PgBouncer) that close stale conns;
    # ``pool_pre_ping`` validates a checked-out connection before use.
    # The default ceiling (``pool_size + max_overflow = 50``) is sized
    # above FastAPI's AnyIO threadpool (~40 workers by default) so sync
    # routes that hold a connection per request do not queue on the pool.
    # See ``docs/operations.md`` for the tuning formula.
    db_pool_size: int = 20
    db_max_overflow: int = 30
    db_pool_recycle_seconds: int = 1800
    db_pool_pre_ping: bool = True
    # Maximum request body size accepted by ContentSizeLimitMiddleware.
    # Defaults to 4 MiB; raise it for endpoints that accept attachments.
    max_request_bytes: int = 4 * 1024 * 1024
    auth_jwt_secret_key: str | None = None
    auth_jwt_algorithm: str = "HS256"
    auth_jwt_issuer: str | None = None
    auth_jwt_audience: str | None = None
    # Clock-skew tolerance for JWT validation across multi-replica deployments.
    # A small leeway (≤60 s) prevents spurious 401s when server clocks drift.
    auth_jwt_leeway_seconds: int = 10
    auth_access_token_expire_minutes: int = 15
    auth_refresh_token_expire_days: int = 30
    auth_cookie_secure: bool = False
    auth_cookie_samesite: Literal["lax", "strict", "none"] = "strict"
    auth_password_reset_token_expire_minutes: int = 30
    auth_email_verify_token_expire_minutes: int = 1440
    auth_rate_limit_enabled: bool = True
    auth_require_distributed_rate_limit: bool = False
    auth_rbac_enabled: bool = True
    auth_require_email_verification: bool = False
    auth_seed_on_startup: bool = False
    auth_bootstrap_super_admin_email: str | None = None
    auth_bootstrap_super_admin_password: str | None = None
    auth_default_user_role: str = "user"
    auth_super_admin_role: str = "super_admin"
    # TODO: OAuth login is not implemented yet. These settings only reserve
    # names for future work; startup logs a warning if any are configured.
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
    # TTL in seconds for the in-process principal cache. Set to 0 to disable
    # caching entirely. When Redis is configured, a Redis-backed cache is used
    # instead and this value controls its TTL.
    auth_principal_cache_ttl_seconds: int = 5
    # ---------------------------------------------------------------------------
    # Email
    # ---------------------------------------------------------------------------
    # ``console`` logs the rendered email (dev/test default). ``smtp`` uses
    # smtplib to dispatch via the configured server. ``resend`` POSTs to
    # Resend's HTTP API. The production validator refuses ``console`` when
    # ``APP_ENVIRONMENT=production``.
    email_backend: Literal["console", "smtp", "resend"] = "console"
    email_from: str | None = None
    email_smtp_host: str | None = None
    email_smtp_port: int = 587
    email_smtp_username: str | None = None
    email_smtp_password: str | None = None
    # STARTTLS upgrade on submission port (587) is the common case. Set
    # ``email_smtp_use_ssl`` instead for implicit-TLS on port 465 — the
    # two are mutually exclusive at the transport level.
    email_smtp_use_starttls: bool = True
    email_smtp_use_ssl: bool = False
    email_smtp_timeout_seconds: float = 10.0
    # Resend HTTP backend. ``email_resend_api_key`` is required when
    # ``email_backend=resend``. ``email_resend_base_url`` defaults to the
    # US endpoint; switch to ``https://api.eu.resend.com`` for the EU
    # data plane or point at a self-hosted Resend-compatible service.
    email_resend_api_key: str | None = None
    email_resend_base_url: str = "https://api.resend.com"
    # ---------------------------------------------------------------------------
    # Background jobs
    # ---------------------------------------------------------------------------
    # ``in_process`` runs handlers inline at enqueue time (dev/test default).
    # ``arq`` enqueues onto Redis for the worker process to consume. The
    # production validator refuses ``in_process`` when ``APP_ENVIRONMENT=production``
    # because losing the web process would lose every queued job.
    jobs_backend: Literal["in_process", "arq"] = "in_process"
    # Falls back to ``APP_AUTH_REDIS_URL`` at composition time if unset, so
    # single-Redis deployments can leave this alone. Setting it explicitly
    # lets the queue and the rate limiter use different Redis instances.
    jobs_redis_url: str | None = None
    jobs_queue_name: str = "arq:queue"
    # arq worker tunables. ``keep_result_seconds_default`` bounds Redis memory
    # for ``arq:queue:result:*`` keys; handlers that need longer retention
    # (e.g. payment-idempotency replay windows) override this per-handler.
    jobs_keep_result_seconds_default: int = 300
    jobs_max_jobs: int = 16
    jobs_job_timeout_seconds: int = 600
    # ---------------------------------------------------------------------------
    # Transactional outbox
    # ---------------------------------------------------------------------------
    # When enabled, request-path consumers (e.g. ``RequestPasswordReset``)
    # write side-effect intents into ``outbox_messages`` inside the same
    # SQL transaction as the business state, and the worker's relay tick
    # claims pending rows and dispatches them through ``JobQueuePort``.
    # Production refuses ``enabled=false`` because the use cases call
    # ``OutboxPort.enqueue`` unconditionally; with the relay off, those
    # rows would accumulate without ever being delivered.
    outbox_enabled: bool = False
    outbox_relay_interval_seconds: float = 5.0
    outbox_claim_batch_size: int = 100
    outbox_max_attempts: int = 8
    # Retry backoff for the relay's per-row failures. The next
    # ``available_at`` is ``now + min(retry_base * 2^(attempts-1), retry_max)``
    # — capped so a single poison row does not burn its entire
    # ``max_attempts`` budget in lockstep 30s ticks.
    outbox_retry_base_seconds: float = 30.0
    outbox_retry_max_seconds: float = 900.0
    # Stamped onto ``outbox_messages.locked_by`` so operators can see which
    # worker holds a row mid-flight. Defaults to ``hostname:pid`` at
    # OutboxSettings construction when unset here.
    outbox_worker_id: str | None = None
    # Retention windows for the prune cron. ``delivered`` rows are
    # best-effort audit trail and are pruned aggressively (7 days
    # default); ``failed`` rows are operator-actionable evidence of
    # dead-lettered work and are kept longer (30 days default). The
    # dedup table (``processed_outbox_messages``) retention is derived
    # from ``retry_max_seconds`` so operators tune one knob.
    outbox_retention_delivered_days: int = 7
    outbox_retention_failed_days: int = 30
    # Maximum rows the prune use case deletes per transaction. The use
    # case loops internally until the eligibility set is empty, so a
    # backlog larger than this value still fully drains — each
    # transaction just stays autovacuum-friendly.
    outbox_prune_batch_size: int = 1000
    # ---------------------------------------------------------------------------
    # File storage
    # ---------------------------------------------------------------------------
    # ``local`` writes to ``APP_STORAGE_LOCAL_PATH`` (dev/test default).
    # ``s3`` uses the bundled ``boto3``-backed adapter; credentials come from
    # the standard AWS chain (env, instance profile, …). Operators pointing
    # at R2/MinIO/other S3-compatible endpoints set ``AWS_ENDPOINT_URL_S3``
    # at the SDK level — no template-specific knob is required.
    # ``storage_enabled`` is the "is a consumer feature actually wired?" flag:
    # the production validator only refuses ``local`` when this is true, so
    # projects that never use file storage are not forced to set up S3.
    storage_enabled: bool = False
    storage_backend: Literal["local", "s3"] = "local"
    # Default points inside the repo so a fresh `.env` (or a stale one that
    # predates this setting) still boots; production deployments override
    # the whole storage stack to `s3` and `validate_production` refuses
    # `local` when ``storage_enabled=True``.
    storage_local_path: str | None = "./var/storage"
    storage_s3_bucket: str | None = None
    storage_s3_region: str = "us-east-1"
    # ---------------------------------------------------------------------------
    # Observability
    # ---------------------------------------------------------------------------
    # When set, OpenTelemetry spans are exported to this OTLP/HTTP endpoint.
    # Example: "http://localhost:4318/v1/traces" (Jaeger / OTel Collector).
    # Leave unset to run with a no-op tracer (zero overhead).
    otel_exporter_endpoint: str | None = None
    otel_service_name: str = "starter-template-fastapi"
    otel_service_version: str = "0.1.0"
    # Head-based sampler ratio in [0.0, 1.0]. 1.0 keeps every trace (dev/test
    # default); production deployments are encouraged to dial this down (e.g.
    # 0.1) so the collector is not flooded under load. When set to 1.0 in
    # production, ``configure_tracing`` emits a warning (it does NOT refuse).
    otel_traces_sampler_ratio: float = 1.0
    # Toggles for the OTel auto-instrumentation libraries registered during
    # ``configure_tracing``. Each defaults to True; flip off to disable the
    # corresponding spans without removing the dependency.
    otel_instrument_sqlalchemy: bool = True
    otel_instrument_httpx: bool = True
    otel_instrument_redis: bool = True
    # Set to false to disable the /metrics Prometheus endpoint.
    metrics_enabled: bool = True
    # Per-dependency timeout for the ``/health/ready`` probe (seconds).
    # Each probe is bounded by this timeout independently and they run
    # in parallel, so the worst-case probe latency is bounded by the
    # slowest single dependency. Kubelet readiness probes typically run
    # every 10 s, so the 1.0 s default leaves a healthy margin. A probe
    # slower than this is itself an "almost-failure" we want to surface.
    health_ready_probe_timeout_seconds: float = 1.0
    # Shared graceful-shutdown budget for the API and the worker. The
    # uvicorn ``--timeout-graceful-shutdown`` flag baked into the
    # production Dockerfile uses this value (currently 30 s in the CMD
    # — keep them in lockstep). The worker's ``on_shutdown`` waits for
    # the in-flight ``DispatchPending`` tick + active job handlers up
    # to this budget before disposing the engine and closing Redis.
    # The K8s ``terminationGracePeriodSeconds`` should be set to this
    # value + a few seconds slack (the inner-process timeout fires
    # first so K8s sees a clean exit instead of SIGKILL).
    shutdown_timeout_seconds: float = 30.0
    # ---------------------------------------------------------------------------
    # Error reporting (Sentry)
    # ---------------------------------------------------------------------------
    # ``APP_SENTRY_DSN`` activates the optional Sentry reporter when the
    # ``sentry`` extra is installed (``pip install '.[sentry]'``). When the
    # DSN is unset, the platform wires the default ``LoggingErrorReporter``
    # which emits a structured WARN log on every unhandled exception.
    # Paging is an operator choice, not a safety invariant — the production
    # validator does NOT refuse start when ``app_sentry_dsn`` is unset.
    app_sentry_dsn: SecretStr | None = None
    app_sentry_environment: str | None = None
    app_sentry_release: str | None = None

    @model_validator(mode="after")
    def _validate_auth_settings(self) -> AppSettings:
        """Validate fields that must be well-formed in every environment.

        Most checks delegate to the per-feature sub-settings classes
        (which own their own ``validate(errors)`` methods); the JWT
        algorithm/leeway range checks stay here because they are platform-
        level invariants with no natural home in a single feature.
        """
        errors: list[str] = []
        if self.auth_jwt_algorithm not in JWT_ALGORITHM_WHITELIST:
            errors.append(
                "APP_AUTH_JWT_ALGORITHM must be one of "
                f"{sorted(JWT_ALGORITHM_WHITELIST)}"
            )
        if not (0 <= self.auth_jwt_leeway_seconds <= MAX_JWT_LEEWAY_SECONDS):
            errors.append("APP_AUTH_JWT_LEEWAY_SECONDS must be between 0 and 60")
        # Email/jobs/storage need to validate their own backend-specific
        # combinations (e.g. ``smtp`` requires a host). Importing the
        # classes lazily keeps :mod:`app_platform.config.settings` free
        # of compile-time dependencies on feature packages so the
        # platform-isolation Import Linter contract stays clean.
        from features.background_jobs.composition.settings import JobsSettings
        from features.email.composition.settings import EmailSettings
        from features.file_storage.composition.settings import StorageSettings
        from features.outbox.composition.settings import OutboxSettings

        EmailSettings.from_app_settings(self).validate(errors)
        JobsSettings.from_app_settings(self).validate(errors)
        StorageSettings.from_app_settings(self).validate(errors)
        OutboxSettings.from_app_settings(self).validate(errors)
        ObservabilitySettings.from_app_settings(self).validate(errors)
        if errors:
            raise ValueError("\n".join(errors))
        return self

    @model_validator(mode="after")
    def _validate_production_settings(self) -> AppSettings:
        """Refuse to start in production if critical settings are missing.

        Delegates to each per-feature sub-settings class' own
        ``validate_production(errors)`` method and aggregates the error
        list into a single :class:`ValueError`. Production-only platform
        checks (database, API, observability) go through the equivalent
        classes in :mod:`app_platform.config.sub_settings`.
        """
        if self.environment != "production":
            return self
        from features.authentication.composition.settings import (
            AuthenticationSettings,
        )
        from features.authorization.composition.settings import (
            AuthorizationSettings,
        )
        from features.background_jobs.composition.settings import JobsSettings
        from features.email.composition.settings import EmailSettings
        from features.file_storage.composition.settings import StorageSettings
        from features.outbox.composition.settings import OutboxSettings
        from features.users.composition.settings import UsersSettings

        errors: list[str] = []
        AuthenticationSettings.from_app_settings(self).validate_production(errors)
        UsersSettings.from_app_settings(self).validate_production(errors)
        AuthorizationSettings.from_app_settings(self).validate_production(errors)
        EmailSettings.from_app_settings(self).validate_production(errors)
        JobsSettings.from_app_settings(self).validate_production(errors)
        StorageSettings.from_app_settings(self).validate_production(errors)
        OutboxSettings.from_app_settings(self).validate_production(errors)
        DatabaseSettings.from_app_settings(self).validate_production(errors)
        ApiSettings.from_app_settings(self).validate_production(errors)
        ObservabilitySettings.from_app_settings(self).validate_production(errors)
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
