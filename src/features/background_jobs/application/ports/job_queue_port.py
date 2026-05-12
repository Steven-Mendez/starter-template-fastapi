"""Inbound port the rest of the application calls to enqueue work.

Two methods cover the starter's needs:

- :meth:`enqueue` — run the named handler "as soon as possible" (the
  in-process adapter runs it inline; the arq adapter pushes onto Redis).
- :meth:`enqueue_at` — run the handler at a specified UTC instant; useful
  for scheduled emails or deferred cleanup.

The contract is intentionally synchronous so existing sync use cases
(``RequestPasswordReset``, ``RequestEmailVerification``) can call it
without changing their signatures. Adapters that talk to async backends
(arq) wrap that internally.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol


class JobQueuePort(Protocol):
    """Enqueue work for later execution by a registered handler."""

    def enqueue(self, job_name: str, payload: dict[str, Any]) -> None:
        """Enqueue ``job_name`` with ``payload`` for immediate execution.

        Raises:
            UnknownJobError: ``job_name`` is not in the handler registry.
        """
        ...

    def enqueue_at(
        self,
        job_name: str,
        payload: dict[str, Any],
        run_at: datetime,
    ) -> None:
        """Enqueue ``job_name`` to run at ``run_at`` (UTC).

        Adapters whose backend has no scheduling semantics (the
        in-process adapter) MAY raise; the contract does not require
        scheduling support on every adapter — only on the adapters that
        ship for production use.
        """
        ...
