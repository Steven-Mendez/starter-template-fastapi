"""CLI: one-shot prune of terminal outbox rows and stale dedup marks.

This module is a project-level composition root (a peer of
``src/main.py`` and ``src/worker.py``). It assembles the minimum
wiring the prune use case needs — a SQL engine and an
:class:`OutboxRepositoryPort` — runs :class:`PruneOutbox` once with
the active settings projection, prints a per-table summary, and exits.

The CLI exercises the same code path the worker's hourly cron does so
operator-driven prunes and scheduled prunes cannot drift.

Invocation::

    uv run python -m cli.outbox_prune

The standard ``APP_*`` env vars configure retention windows and batch
size; the configured ``APP_OUTBOX_ENABLED`` is intentionally **not**
consulted — an operator running the one-shot has already decided to
prune, regardless of whether the worker would have scheduled the same
sweep at the same time.
"""

from __future__ import annotations

import sys

from sqlalchemy import create_engine

from app_platform.config.settings import AppSettings
from features.outbox.adapters.outbound.sqlmodel.repository import (
    SQLModelOutboxRepository,
)
from features.outbox.application.use_cases.maintenance.prune_outbox import PruneOutbox
from features.outbox.composition.settings import OutboxSettings


def run_once() -> int:
    """Execute :class:`PruneOutbox` once and print the summary."""
    app_settings = AppSettings()
    outbox_settings = OutboxSettings.from_app_settings(app_settings)
    engine = create_engine(
        app_settings.postgresql_dsn,
        pool_pre_ping=app_settings.db_pool_pre_ping,
    )
    try:
        repository = SQLModelOutboxRepository(_engine=engine)
        use_case = PruneOutbox(_repository=repository)
        result = use_case.execute(
            retention_delivered_days=outbox_settings.retention_delivered_days,
            retention_failed_days=outbox_settings.retention_failed_days,
            dedup_retention_seconds=outbox_settings.dedup_retention_seconds,
            batch_size=outbox_settings.prune_batch_size,
        )
    finally:
        engine.dispose()

    # ``PruneOutbox.execute`` returns ``Ok`` today (any failure raises
    # through). We unwrap defensively so a future ``Err`` branch
    # surfaces a non-zero exit code instead of silently printing
    # zeros.
    from app_platform.shared.result import Err

    if isinstance(result, Err):
        print(f"outbox prune failed: {result.error!r}", file=sys.stderr)
        return 1
    summary = result.value
    print(
        "outbox prune summary: "
        f"delivered_deleted={summary.delivered_deleted} "
        f"failed_deleted={summary.failed_deleted} "
        f"processed_marks_deleted={summary.processed_marks_deleted}"
    )
    return 0


def main(argv: list[str] | None = None) -> int:  # noqa: ARG001
    """Entry point invoked by ``make outbox-prune``."""
    return run_once()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
