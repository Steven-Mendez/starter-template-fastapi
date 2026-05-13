"""Regression: ``src/main.py`` MUST NOT schedule the outbox relay.

The relay is a worker-only concern. Scheduling it inside the FastAPI
process would mean the web replicas compete for outbox rows on every
request loop iteration, which is exactly the behaviour the worker /
web split is supposed to avoid. The test guards that boundary at the
module-import level so an accidental future edit to ``main.py`` that
imports the relay registrar surfaces immediately.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


def test_main_module_does_not_import_relay_registrar() -> None:
    main_src = Path(__file__).resolve().parents[4] / "main.py"
    body = main_src.read_text(encoding="utf-8")
    assert "build_relay_cron_jobs" not in body, (
        "src/main.py must not register the outbox relay — that is the worker's job. "
        "Move the import into src/worker.py."
    )
