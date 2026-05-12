"""Admin-surface use cases.

Each use case is checked against the ``system:main`` resource by the
HTTP route layer; nothing in this module performs its own authorization.
"""

from src.features.authentication.application.use_cases.admin.list_audit_events import (
    ListAuditEvents,
)

__all__ = [
    "ListAuditEvents",
]
