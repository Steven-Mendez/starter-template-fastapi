"""Persistence-layer exceptions raised across the kanban feature.

Defined in the application layer so adapters (SQLModel, in-memory fakes)
share one exception type and use cases can catch it without importing
from a specific outbound adapter.
"""

from __future__ import annotations


class PersistenceConflictError(RuntimeError):
    """Raised when a stale aggregate write is detected (optimistic-lock failure)."""
