"""FastAPI factory that wires platform-level middleware and error handlers.

The factory is deliberately stateless: it returns a fresh app configured
with CORS, trusted-host filtering, request-context logging, and Problem
Details error handlers. Lifespan, container wiring, and feature
registration are left to the caller in ``main.py`` so the platform layer
stays unaware of which features are mounted.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app_platform.api.error_handlers import register_problem_details
from app_platform.api.middleware.access_log import AccessLogMiddleware
from app_platform.api.middleware.content_size_limit import ContentSizeLimitMiddleware
from app_platform.api.middleware.request_context import RequestContextMiddleware
from app_platform.api.middleware.security_headers import SecurityHeadersMiddleware
from app_platform.api.operation_ids import feature_operation_id
from app_platform.api.root import root_router
from app_platform.config.settings import AppSettings
from app_platform.observability.error_reporter import (
    ErrorReporterPort,
    LoggingErrorReporter,
    SentryErrorReporter,
)
from app_platform.observability.metrics import configure_metrics

__all__ = ["build_fastapi_app", "feature_operation_id"]

_logger = logging.getLogger("api.error.reporter")


def _select_error_reporter(settings: AppSettings) -> ErrorReporterPort:
    """Pick the reporter per the rule documented in ``design.md``.

    1. ``APP_SENTRY_DSN`` set AND ``sentry_sdk`` importable →
       :class:`SentryErrorReporter`. Also calls ``sentry_sdk.init(...)``
       so the SDK is configured before the first ``capture_exception``.
       ``traces_sample_rate`` is tied to ``APP_OTEL_TRACES_SAMPLER_RATIO``
       so OTel and Sentry sampling agree.
    2. ``APP_SENTRY_DSN`` set AND ``sentry_sdk`` NOT importable →
       :class:`LoggingErrorReporter` plus a WARN log naming the missing
       optional extra (``pip install '.[sentry]'``).
    3. ``APP_SENTRY_DSN`` unset → :class:`LoggingErrorReporter` plus an
       INFO log naming the chosen reporter.
    """
    dsn = settings.app_sentry_dsn
    if dsn is None:
        _logger.info(
            "event=error_reporter.selected reporter=logging reason=app_sentry_dsn_unset"
        )
        return LoggingErrorReporter()

    try:
        reporter = SentryErrorReporter()
    except ModuleNotFoundError:
        _logger.warning(
            "event=error_reporter.fallback reporter=logging "
            "reason=sentry_sdk_not_installed "
            "remediation=\"pip install '.[sentry]'\""
        )
        return LoggingErrorReporter()

    # Initialize the SDK now that we know it imported cleanly. We use a
    # late import to keep this module loadable when the extra is absent.
    import sentry_sdk

    sentry_sdk.init(
        dsn=dsn.get_secret_value(),
        environment=settings.app_sentry_environment,
        release=settings.app_sentry_release,
        traces_sample_rate=settings.otel_traces_sampler_ratio,
    )
    _logger.info(
        "event=error_reporter.selected reporter=sentry "
        "environment=%s release=%s traces_sample_rate=%s",
        settings.app_sentry_environment,
        settings.app_sentry_release,
        settings.otel_traces_sampler_ratio,
    )
    return reporter


def build_fastapi_app(settings: AppSettings) -> FastAPI:
    """Return FastAPI with platform middleware and error handlers.

    Lifespan, container wiring and feature registration remain the
    caller's responsibility, keeping the platform layer feature-agnostic.
    """
    docs_url = "/docs" if settings.enable_docs else None
    redoc_url = "/redoc" if settings.enable_docs else None
    openapi_url = "/openapi.json" if settings.enable_docs else None

    app = FastAPI(
        title="starter-template-fastapi",
        description="FastAPI starter service",
        version="0.1.0",
        openapi_url=openapi_url,
        docs_url=docs_url,
        redoc_url=redoc_url,
    )

    # Starlette executes middleware in reverse-add order: the LAST added
    # is the OUTERMOST. We add innermost-first so the runtime chain is:
    #
    #   request → CORS → TrustedHost → SecurityHeaders → GZip
    #          → ContentSizeLimit → RequestContext → AccessLog → router
    #
    # Order rationale:
    # * CORS is outermost so OPTIONS preflight short-circuits before any
    #   inner check (a preflight from a disallowed host shouldn't trip
    #   TrustedHost or content-size guards).
    # * TrustedHost runs next so unknown hosts are dropped before we
    #   spend cycles measuring body size or stamping headers.
    # * SecurityHeaders sits OUTSIDE ContentSizeLimit so the strict CSP /
    #   Referrer-Policy / X-Content-Type-Options / Permissions-Policy
    #   headers are also attached to 400 / 411 / 413 short-circuit
    #   responses from ContentSizeLimit — every response carries the
    #   baseline regardless of which layer terminated it.
    # * GZip sits between SecurityHeaders and ContentSizeLimit. It only
    #   honours ``minimum_size`` when the inner response is
    #   non-streaming, which is why SecurityHeaders, RequestContext, and
    #   ContentSizeLimit are implemented as pure ASGI middlewares (not
    #   ``BaseHTTPMiddleware``-derived). Compression fires for payloads
    #   ≥ 1024 bytes so small replies skip the CPU cost.
    # * ContentSizeLimit wraps the application so 411/413 fire before
    #   the inner handler ever sees the request.
    # * RequestContext stamps the request id onto ``scope["state"]`` and
    #   the ``REQUEST_ID_CONTEXT`` contextvar BEFORE AccessLog runs, so
    #   the access log line correctly carries the request id (uvicorn's
    #   built-in access log fires outside that contextvar window and is
    #   disabled in :mod:`app_platform.observability.logging`).
    # * AccessLog is innermost so it sees the final response status set
    #   by the inner handler.
    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(ContentSizeLimitMiddleware, max_bytes=settings.max_request_bytes)
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    app.add_middleware(
        SecurityHeadersMiddleware,
        hsts=(settings.environment == "production"),
        docs_enabled=settings.enable_docs,
    )

    if settings.environment != "development":
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=settings.trusted_hosts,
        )

    if settings.cors_origins == ["*"]:
        # Wildcard origins cannot be combined with allow_credentials=True per the
        # CORS spec. This open mode is intentional for local development only.
        # Production settings validation (AppSettings._validate_production_settings)
        # rejects cors_origins=["*"], so this branch is unreachable in production.
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=False,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    elif settings.cors_origins:
        # Credentialed CORS: enumerate methods and headers explicitly
        # rather than reflecting the request. Wildcards work with
        # credentials in some browsers, but the enumeration tightens
        # what cross-origin JS can probe and is the OWASP-recommended
        # posture. ``expose_headers`` lets SPAs read ``X-Request-ID``
        # (for log correlation) and ``Retry-After`` (for rate-limit
        # backoff) from JS without preflight indirection.
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
            expose_headers=["X-Request-ID", "Retry-After"],
        )

    # ProxyHeadersMiddleware MUST be the outermost middleware: it
    # rewrites ``scope["client"]`` from ``X-Forwarded-For`` before any
    # downstream code reads ``request.client.host`` (the auth rate
    # limiter, audit logs, access logs, …). Because Starlette executes
    # middleware in reverse-add order, "outermost" means added LAST.
    #
    # ``trusted_hosts`` accepts CIDR ranges. The production validator
    # in ``ApiSettings.validate_production`` refuses an empty list — a
    # deploy that forgets this setting fails to boot rather than
    # quietly letting one attacker exhaust the rate-limit bucket for
    # the entire user base. In development the list is typically empty
    # (no proxy in front), so the middleware is a no-op: with an empty
    # ``trusted_hosts`` set it never rewrites ``scope["client"]``.
    #
    # The setting must NEVER be ``0.0.0.0/0`` — that lets any caller
    # spoof ``X-Forwarded-For`` and bypass per-IP limits. Documented in
    # ``.env.example`` and ``docs/operations.md``.
    if settings.trusted_proxy_ips:
        app.add_middleware(
            ProxyHeadersMiddleware,
            trusted_hosts=settings.trusted_proxy_ips,
        )

    # Select the error reporter before installing error handlers so the
    # unhandled-exception handler always sees a non-None reporter on
    # ``app.state.error_reporter``.
    app.state.error_reporter = _select_error_reporter(settings)

    register_problem_details(app, settings)
    app.include_router(root_router)
    configure_metrics(app, enabled=settings.metrics_enabled)
    return app
