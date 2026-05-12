"""Auth feature composition helpers."""

from src.features.authentication.composition.app_state import (
    AUTH_CONTAINER_ATTR,
    get_auth_container,
    set_auth_container,
)
from src.features.authentication.composition.container import (
    AuthContainer,
    build_auth_container,
)

__all__ = [
    "AUTH_CONTAINER_ATTR",
    "AuthContainer",
    "build_auth_container",
    "get_auth_container",
    "set_auth_container",
]
