"""Composition root for the authorization feature."""

from __future__ import annotations

from features.authorization.composition.container import (
    AuthorizationContainer,
    build_authorization_container,
)
from features.authorization.composition.wiring import (
    attach_authorization_container,
    register_authorization_error_handlers,
)

__all__ = [
    "AuthorizationContainer",
    "attach_authorization_container",
    "build_authorization_container",
    "register_authorization_error_handlers",
]
