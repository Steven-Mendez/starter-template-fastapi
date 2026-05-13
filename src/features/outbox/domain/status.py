"""Lifecycle states a row in ``outbox_messages`` may hold.

The relay flips a row through these states in a strict order:

- ``pending`` — written by a producer transaction, awaiting dispatch.
- ``delivered`` — successfully handed off to ``JobQueuePort`` and the
  per-row transaction committed.
- ``failed`` — permanently abandoned after exhausting the retry budget.

Operators inspect the table by status. Failed rows surface to a human
via the documented ``SELECT ... WHERE status='failed'`` query and can
be re-armed with the ``outbox-retry-failed`` Makefile target.
"""

from __future__ import annotations

from typing import Literal

OutboxStatus = Literal["pending", "delivered", "failed"]
