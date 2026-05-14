"""Reusable OpenAPI ``responses=`` dicts for Problem Details error branches.

FastAPI emits an OpenAPI ``responses`` entry only for status codes
declared on the route decorator. Without this, generated OpenAPI shows
only the happy-path status codes, leaving SDK generators no way to
surface the typed error shape clients actually see at runtime.

This module defines :data:`PROBLEM_RESPONSES` — the union of every 4xx
status the service emits — plus per-feature subsets that each router
spreads into its decorators. The :data:`PROBLEM_RESPONSES` map and the
runtime renderer (:func:`app_platform.api.error_handlers.problem_json_response`)
share the same shape: :class:`ProblemDetails`.

Usage::

    from app_platform.api.responses import AUTH_RESPONSES

    @router.post("/login", response_model=TokenResponse, responses=AUTH_RESPONSES)
    def login(...): ...
"""

from __future__ import annotations

from typing import Any

from app_platform.api.schemas import ProblemDetails

# Inline copy of the ``application/problem+json`` media type so this
# module avoids importing ``app_platform.api.error_handlers`` (which
# pulls in ``AppSettings`` and, transitively, every feature's settings
# module). Keeping ``responses`` decoupled from that chain lets feature
# adapters reuse the constants without crossing import-linter
# boundaries.
PROBLEM_JSON = "application/problem+json"


def _problem_response(description: str) -> dict[str, Any]:
    """Build a single OpenAPI response entry for a Problem Details branch.

    Every 4xx response the service emits uses the ``application/problem+json``
    media type and serialises through :class:`ProblemDetails`. Centralising
    the construction here keeps each entry identical except for ``description``.
    """
    return {
        "model": ProblemDetails,
        "description": description,
        "content": {
            PROBLEM_JSON: {
                "schema": {"$ref": "#/components/schemas/ProblemDetails"},
            },
        },
    }


# Every 4xx code the service may emit. Per-feature subsets below pick
# the ones their routers actually return so generated OpenAPI does not
# advertise branches that can't happen.
PROBLEM_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: _problem_response("Malformed request (e.g. invalid cursor)."),
    401: _problem_response("Authentication required or token invalid."),
    403: _problem_response("Authenticated but not authorized for this resource."),
    404: _problem_response("Resource not found."),
    409: _problem_response("Conflict with current resource state."),
    422: _problem_response("Request validation failed."),
    429: _problem_response("Rate limit exceeded."),
}


# Per-feature subsets. These are the explicit error branches each
# router declares; keeping them as named constants makes the per-route
# decorator line short (``responses=AUTH_RESPONSES``).
AUTH_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: PROBLEM_RESPONSES[401],
    403: PROBLEM_RESPONSES[403],
    409: PROBLEM_RESPONSES[409],
    422: PROBLEM_RESPONSES[422],
    429: PROBLEM_RESPONSES[429],
}

USERS_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: PROBLEM_RESPONSES[401],
    403: PROBLEM_RESPONSES[403],
    404: PROBLEM_RESPONSES[404],
    422: PROBLEM_RESPONSES[422],
}

ADMIN_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: PROBLEM_RESPONSES[400],
    401: PROBLEM_RESPONSES[401],
    403: PROBLEM_RESPONSES[403],
    404: PROBLEM_RESPONSES[404],
    422: PROBLEM_RESPONSES[422],
}

ROOT_RESPONSES: dict[int | str, dict[str, Any]] = {
    # Root/health endpoints take no body and no auth — there is no 4xx
    # branch worth declaring beyond the platform-level catch-alls
    # already handled by the global exception handlers.
}
