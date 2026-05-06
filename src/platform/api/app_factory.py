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
from src.platform.api.middleware.request_context import RequestContextMiddleware
from src.platform.api.root import root_router
from src.platform.config.settings import AppSettings


def build_fastapi_app(settings: AppSettings) -> FastAPI:
    """Return FastAPI with platform middleware and error handlers.

    Lifespan, container wiring and feature registration remain the
    caller's responsibility, keeping the platform layer feature-agnostic.
    """
    docs_url = "/docs" if settings.enable_docs else None
    redoc_url = "/redoc" if settings.enable_docs else None

    app = FastAPI(
        title="starter-template-fastapi",
        description="FastAPI starter service",
        version="0.1.0",
        docs_url=docs_url,
        redoc_url=redoc_url,
    )

    if settings.cors_origins == ["*"]:
        # Starlette cannot combine credentialed CORS with a literal wildcard
        # origin, so the regex path makes it echo the requesting origin.
        app.add_middleware(
            CORSMiddleware,
            allow_origin_regex=".*",
            allow_credentials=True,
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

    if settings.environment != "development":
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=settings.trusted_hosts,
        )

    app.add_middleware(RequestContextMiddleware)
    register_problem_details(app)
    app.include_router(root_router)
    return app
