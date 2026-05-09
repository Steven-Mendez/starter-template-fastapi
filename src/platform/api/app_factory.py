"""FastAPI factory that wires platform-level middleware and error handlers.

The factory is deliberately stateless: it returns a fresh app configured
with CORS, trusted-host filtering, request-context logging, and Problem
Details error handlers. Lifespan, container wiring, and feature
registration are left to the caller in ``main.py`` so the platform layer
stays unaware of which features are mounted.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from src.platform.api.error_handlers import register_problem_details
from src.platform.api.middleware.content_size_limit import ContentSizeLimitMiddleware
from src.platform.api.middleware.request_context import RequestContextMiddleware
from src.platform.api.middleware.security_headers import SecurityHeadersMiddleware
from src.platform.api.root import root_router
from src.platform.config.settings import AppSettings
from src.platform.observability.metrics import configure_metrics


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
    #   request → CORS → TrustedHost → ContentSizeLimit
    #          → SecurityHeaders → RequestContext → router
    #
    # Order rationale:
    # * CORS is outermost so OPTIONS preflight short-circuits before any
    #   inner check (a preflight from a disallowed host shouldn't trip
    #   TrustedHost or content-size guards).
    # * TrustedHost runs next so unknown hosts are dropped before we
    #   spend cycles measuring body size or stamping headers.
    # * ContentSizeLimit and SecurityHeaders wrap the application proper.
    # * RequestContext is innermost so its access log records the final
    #   response status set by the inner handler.
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        SecurityHeadersMiddleware,
        hsts=(settings.environment == "production"),
    )
    app.add_middleware(ContentSizeLimitMiddleware, max_bytes=settings.max_request_bytes)

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
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    register_problem_details(app, settings)
    app.include_router(root_router)
    configure_metrics(app, enabled=settings.metrics_enabled)
    return app
