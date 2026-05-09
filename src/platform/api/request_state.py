"""Typed contract for per-request state shared across features.

Auth writes ``actor_id`` after validating a JWT; kanban reads it to stamp
audit columns without importing from the auth feature directly.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import Request


class RequestState:
    """Typed view of ``request.state`` attributes shared across features."""

    actor_id: UUID | None


def set_actor_id(request: Request, actor_id: UUID | None) -> None:
    """Write the authenticated actor's UUID to request state."""
    request.state.actor_id = actor_id


def get_actor_id(request: Request) -> UUID | None:
    """Read the authenticated actor's UUID from request state.

    Returns ``None`` when auth is not wired (anonymous deployment) or the
    request has not been authenticated — the same semantics as the previous
    ``getattr(request.state, "actor_id", None)`` call sites.
    """
    return getattr(request.state, "actor_id", None)
