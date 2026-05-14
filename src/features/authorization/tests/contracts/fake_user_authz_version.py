"""In-memory fake for ``UserAuthzVersionPort`` used by authorization tests.

The fake records every ``bump`` call so tests can assert on the set of
user ids touched without needing a real ``users`` table.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID


@dataclass(slots=True)
class FakeUserAuthzVersionPort:
    """Records each ``bump(user_id)`` call in ``bumped``.

    Also tracks a per-user counter so :meth:`read_version` reflects every
    :meth:`bump` / :meth:`bump_in_session` call — that is the probe the
    strengthened contract relies on to assert ``bump`` actually
    increments rather than silently passing.
    """

    bumped: list[UUID] = field(default_factory=list)
    _versions: dict[UUID, int] = field(default_factory=dict)

    def bump(self, user_id: UUID) -> None:
        self.bumped.append(user_id)
        self._versions[user_id] = self._versions.get(user_id, 0) + 1

    def bump_in_session(self, session: Any, user_id: UUID) -> None:
        """Records ``bump_in_session`` calls in the same ``bumped`` list.

        The fake ignores the session — tests that care about transactional
        atomicity use the real SQLModel adapter via the integration suite.
        """
        del session
        self.bumped.append(user_id)
        self._versions[user_id] = self._versions.get(user_id, 0) + 1

    def read_version(self, user_id: UUID) -> int:
        """Return the current authz_version, ``0`` if the user is unknown."""
        return self._versions.get(user_id, 0)
