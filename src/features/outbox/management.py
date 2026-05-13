"""Operator entrypoint for the outbox feature.

Currently exposes only ``retry-failed``: resets every row in
``status='failed'`` back to ``pending`` with ``attempts=0`` so the
next relay tick claims and retries them. Documented in
``docs/outbox.md``; invoked by ``make outbox-retry-failed``.
"""

from __future__ import annotations

import argparse
import logging
import sys

from sqlalchemy import create_engine, text

from app_platform.config.settings import get_settings

_logger = logging.getLogger("features.outbox.management")


def retry_failed() -> int:
    """Reset failed outbox rows to ``pending`` for another retry budget."""
    settings = get_settings()
    engine = create_engine(settings.postgresql_dsn, pool_pre_ping=True)
    try:
        with engine.begin() as conn:
            result = conn.execute(
                text(
                    """
                    UPDATE outbox_messages
                    SET status = 'pending',
                        attempts = 0,
                        last_error = NULL,
                        available_at = now(),
                        locked_at = NULL,
                        locked_by = NULL
                    WHERE status = 'failed'
                    """
                )
            )
            count = result.rowcount or 0
        _logger.info("event=outbox.retry_failed rows=%d", count)
        return int(count)
    finally:
        engine.dispose()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="outbox")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("retry-failed", help="Re-arm failed outbox rows.")
    args = parser.parse_args(argv)
    if args.command == "retry-failed":
        count = retry_failed()
        print(f"Reset {count} failed outbox row(s).")
        return 0
    return 1  # pragma: no cover - argparse rejects unknown subcommands first


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
