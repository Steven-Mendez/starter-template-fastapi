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
    """Records each ``bump(user_id)`` call in ``bumped``."""

    bumped: list[UUID] = field(default_factory=list)

    def bump(self, user_id: UUID) -> None:
        self.bumped.append(user_id)

    def bump_in_session(self, session: Any, user_id: UUID) -> None:
        """Records ``bump_in_session`` calls in the same ``bumped`` list.

        The fake ignores the session — tests that care about transactional
        atomicity use the real SQLModel adapter via the integration suite.
        """
        del session
        self.bumped.append(user_id)
