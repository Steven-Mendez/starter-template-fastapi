from __future__ import annotations

import json
import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from dependencies import build_container, get_app_container, set_app_container
from kanban.router import router as kanban_router
from problem_details import register_problem_details
from settings import AppSettings, get_settings


def _close_if_supported(resource: object) -> None:
    close = getattr(resource, "close", None)
    if callable(close):
        close()


def create_app(settings: AppSettings | None = None) -> FastAPI:
    app_settings = settings or get_settings()
    docs_url = "/docs" if app_settings.enable_docs else None
    redoc_url = "/redoc" if app_settings.enable_docs else None

    @asynccontextmanager
    async def lifespan(lifespan_app: FastAPI) -> AsyncIterator[None]:
        container = build_container(app_settings)
        set_app_container(lifespan_app, container)
        yield
        _close_if_supported(container.repository)
        lifespan_app.state.container = None

    app = FastAPI(
        title="starter-template-fastapi",
        description="FastAPI starter service",
        version="0.1.0",
        docs_url=docs_url,
        redoc_url=redoc_url,
        lifespan=lifespan,
    )

    if app_settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=app_settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    if app_settings.environment != "development":
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=app_settings.trusted_hosts,
        )

    register_problem_details(app)
    app.include_router(kanban_router)
    logger = logging.getLogger("api.request")

    @app.middleware("http")
    async def request_context_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        started = time.perf_counter()
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        logger.info(
            json.dumps(
                {
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": elapsed_ms,
                }
            )
        )
        return response

    @app.get("/")
    def read_root() -> dict[str, str]:
        return {
            "name": "starter-template-fastapi",
            "message": "FastAPI service is running.",
        }

    @app.get("/health")
    def health(request: Request) -> dict[str, object]:
        container = get_app_container(request)
        ready = container.repository.is_ready()
        return {
            "status": "ok" if ready else "degraded",
            "persistence": {
                "backend": container.settings.repository_backend,
                "ready": ready,
            },
        }

    return app


app = create_app()
