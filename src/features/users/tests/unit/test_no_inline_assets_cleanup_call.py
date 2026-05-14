"""Static assertion: deactivate/erase use cases never call cleanup inline.

The architectural contract is that asset cleanup is *always* enqueued
through the outbox and executed by the worker handler. A direct call
to :meth:`UserAssetsCleanupPort.delete_user_assets` from
``deactivate_user.py`` (or, when it lands, ``erase_user.py``) would
couple the HTTP path to storage-backend latency and bypass the
worker's exponential backoff on transient failures.

The scan is intentionally textual: a structural AST walk would have
to model attribute resolution to be more precise, and a textual
prohibition is the same shape the spec calls for.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import features.users.application.use_cases.deactivate_user as deactivate_user_module
import features.users.application.use_cases.erase_user as erase_user_module

pytestmark = pytest.mark.unit


_FORBIDDEN_TOKEN = "delete_user_assets("
_ALLOWED_REFERENCES = {
    # The job-name constant is allowed (and required) — it is how the
    # handler ↔ producer agreement is enforced.
    "DELETE_USER_ASSETS_JOB",
}


def _source_for_module(module: object) -> str:
    module_file = getattr(module, "__file__", None)
    assert module_file is not None
    return Path(module_file).read_text(encoding="utf-8")


def test_deactivate_user_does_not_call_cleanup_port_directly() -> None:
    source = _source_for_module(deactivate_user_module)
    assert _FORBIDDEN_TOKEN not in source, (
        "DeactivateUser must enqueue ``delete_user_assets`` through the outbox, "
        "never call UserAssetsCleanupPort.delete_user_assets inline."
    )
    # The job-name constant should appear — that is the only allowed
    # reference to the string ``delete_user_assets`` in the use case.
    for allowed in _ALLOWED_REFERENCES:
        assert allowed in source


def test_erase_user_does_not_call_cleanup_port_directly() -> None:
    """``EraseUser`` enqueues asset cleanup through the outbox, never inline.

    The same architectural rule applies as for ``DeactivateUser``:
    storage-backend latency must never block the request transaction,
    and the cleanup must benefit from the worker's retry backoff.
    """
    source = _source_for_module(erase_user_module)
    assert _FORBIDDEN_TOKEN not in source, (
        "EraseUser must enqueue ``delete_user_assets`` through the outbox, "
        "never call UserAssetsCleanupPort.delete_user_assets inline."
    )
    for allowed in _ALLOWED_REFERENCES:
        assert allowed in source
