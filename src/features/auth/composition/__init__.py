"""Auth feature composition helpers."""

from src.features.auth.composition.app_state import (
    AUTH_CONTAINER_ATTR,
    get_auth_container,
    set_auth_container,
)
from src.features.auth.composition.container import AuthContainer, build_auth_container
from src.features.auth.composition.wiring import (
    attach_auth_container,
    mount_auth_routes,
    register_auth,
)

__all__ = [
    "AUTH_CONTAINER_ATTR",
    "AuthContainer",
    "attach_auth_container",
    "build_auth_container",
    "get_auth_container",
    "mount_auth_routes",
    "register_auth",
    "set_auth_container",
]
