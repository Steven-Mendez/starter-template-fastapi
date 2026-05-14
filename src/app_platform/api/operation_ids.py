"""Stable ``operationId`` generation for OpenAPI.

FastAPI's default ``generate_unique_id`` produces ``{tag}-{name}-{path}``
which contains slashes and dashes — values that break some SDK generators
and that change every time a route's path changes.

This module defines :func:`feature_operation_id`, the convention used
across the service: ``{router_tag}_{handler_name}`` in snake_case, where
``router_tag`` is the router's first tag (or ``root`` if none is set)
and ``handler_name`` is the snake_case Python name of the handler
function (preserved by FastAPI on ``route.name``).

The function is installed on every ``APIRouter`` via the router's
``generate_unique_id_function`` kwarg so the convention applies
uniformly across the service.

Examples produced::

    POST /auth/login         → auth_login
    GET /me                  → users_get_me
    PATCH /me                → users_patch_me
    GET /admin/users         → users_admin_list_users
    GET /admin/audit-log     → auth_admin_list_audit_events
    GET /health/live         → health_liveness
"""

from __future__ import annotations

from fastapi.routing import APIRoute


def feature_operation_id(route: APIRoute) -> str:
    """Return the stable ``operationId`` for ``route``.

    The convention is ``{router_tag}_{handler_name}`` in snake_case,
    where ``router_tag`` is the router's first tag (or ``root`` if
    unset). Handler names are already snake_case in this codebase, so
    no transformation is applied to ``route.name``.
    """
    tag = route.tags[0] if route.tags else "root"
    return f"{tag}_{route.name}"
