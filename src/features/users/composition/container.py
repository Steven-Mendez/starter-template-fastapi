"""Composition root for the users feature.

The container is intentionally small. The two outbound-port adapters that
authorization consumes (``SQLModelUserRegistrarAdapter`` and
``SQLModelUserAuthzVersionAdapter``) physically live under
``src.features.users.adapters.outbound`` but are still constructed by
the authentication feature's container in this transitional state.
That coupling is removed when the credentials split lands in PR 5/6 of
the foundation change.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.engine import Engine

from src.features.users.adapters.outbound.persistence.sqlmodel.repository import (
    SQLModelUserRepository,
)


@dataclass(slots=True)
class UsersContainer:
    """Bundle of singletons for the users feature."""

    user_repository: SQLModelUserRepository

    def shutdown(self) -> None:
        # The engine is shared with the authentication container; it is
        # disposed there. Nothing per-feature to release.
        return None


def build_users_container(*, engine: Engine) -> UsersContainer:
    """Construct the users container sharing the auth engine."""
    return UsersContainer(user_repository=SQLModelUserRepository(engine=engine))
