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


def test_erase_user_is_not_yet_in_tree() -> None:
    """``EraseUser`` ships in ``add-gdpr-erasure-and-export``.

    When that change lands, this test should be replaced with a real
    scan of ``erase_user.py``. Tracking the deferred work with a live
    test means the omission cannot silently outlive the next change.
    """
    module_file = deactivate_user_module.__file__
    assert module_file is not None
    erase_user_path = Path(module_file).parent / "erase_user.py"
    assert not erase_user_path.exists(), (
        "erase_user.py now exists — extend the static scan to cover it. "
        "See openspec change ``add-gdpr-erasure-and-export``."
    )
