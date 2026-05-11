"""In-memory fake for ``UserAuthzVersionPort`` used by authorization tests.

The fake records every ``bump`` call so tests can assert on the set of
user ids touched without needing a real ``users`` table.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID


@dataclass(slots=True)
class FakeUserAuthzVersionPort:
    """Records each ``bump(user_id)`` call in ``bumped``."""

    bumped: list[UUID] = field(default_factory=list)

    def bump(self, user_id: UUID) -> None:
        self.bumped.append(user_id)
