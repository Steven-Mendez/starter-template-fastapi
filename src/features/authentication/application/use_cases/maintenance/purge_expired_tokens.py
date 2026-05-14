"""Maintenance use case: purge expired refresh and internal token rows.

Two authentication tables grow forever if left alone:

- ``refresh_tokens`` — ``LogoutUser`` and rotation only stamp
  ``revoked_at`` / ``replaced_by_token_id``; rows past ``expires_at``
  also stay on disk indefinitely.
- ``auth_internal_tokens`` — password-reset and email-verify tokens
  are stamped ``used_at`` (or left unused past ``expires_at``) but
  nothing ever deletes them.

After a few months of modest traffic both tables grow into the
millions; indexes bloat, backups slow down. :class:`PurgeExpiredTokens`
sweeps each table in 10k-row batches so a single tick never holds a
long transaction or starves autovacuum. The retention window is a
settings knob; the default (7 days) is short enough to keep tables
small and long enough to investigate "did the user really log out at
time X?" incidents.

Designed to run from the worker's arq cron — see
``src/worker.py``'s registration of ``auth-purge-tokens``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app_platform.shared.result import Ok, Result
from features.authentication.application.errors import AuthError
from features.authentication.application.ports.outbound.auth_repository import (
    AuthRepositoryPort,
)

_logger = logging.getLogger("features.authentication.maintenance")


@dataclass(frozen=True, slots=True)
class PurgeReport:
    """Per-table counts emitted by a single :class:`PurgeExpiredTokens` tick."""

    refresh_tokens_deleted: int
    internal_tokens_deleted: int


@dataclass(slots=True)
class PurgeExpiredTokens:
    """Sweep expired refresh- and internal-token rows in bounded batches."""

    _repository: AuthRepositoryPort

    def execute(self, retention_days: int) -> Result[PurgeReport, AuthError]:
        """Delete eligible rows from both token tables.

        Args:
            retention_days: Retention window. Rows whose ``expires_at``
                or ``revoked_at`` / ``used_at`` is older than ``now() -
                retention_days`` are eligible for deletion.

        Returns:
            ``Ok(PurgeReport)`` with the total number of rows deleted
            from each table. The repository implementation loops in
            10k-row batches per table until the eligibility set is
            empty so the total deletion is unbounded across iterations
            even when each transaction is small.
        """
        cutoff = datetime.now(UTC) - timedelta(days=retention_days)

        refresh_deleted = self._repository.delete_expired_refresh_tokens(cutoff)
        internal_deleted = self._repository.delete_expired_internal_tokens(cutoff)

        report = PurgeReport(
            refresh_tokens_deleted=refresh_deleted,
            internal_tokens_deleted=internal_deleted,
        )
        _logger.info(
            "event=auth.purge_expired_tokens.tick "
            "retention_days=%d refresh_tokens_deleted=%d "
            "internal_tokens_deleted=%d",
            retention_days,
            report.refresh_tokens_deleted,
            report.internal_tokens_deleted,
        )
        return Ok(report)
