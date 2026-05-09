"""Framework-agnostic authorization contracts for the platform layer."""

from __future__ import annotations

from typing import Any, Protocol

from src.platform.shared.principal import Principal


class ResolvePrincipalCallable(Protocol):
    """Callable that resolves a raw bearer token into a ``Principal``.

    Implementors return ``Result[Principal, Any]`` so the caller can pattern-
    match on ``Ok`` / ``Err`` without importing concrete error types.
    """

    def __call__(self, token: str) -> Any: ...


__all__ = ["Principal", "ResolvePrincipalCallable"]
