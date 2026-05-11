"""Static check: the auth authorization layer never mentions kanban vocabulary.

After ``decouple-authz-from-features``, the authorization engine learns
about resource types only from the runtime registry. This test fails if
a future change re-introduces a kanban-flavoured resource type string
under ``application/authorization/`` or the SQLModel adapter.
"""

from __future__ import annotations

import pathlib

import pytest

pytestmark = pytest.mark.unit

_FORBIDDEN_TOKENS = ('"kanban"', '"column"', '"card"')
_PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[5]
_SCANNED_DIRS = (
    _PROJECT_ROOT / "src" / "features" / "auth" / "application" / "authorization",
    _PROJECT_ROOT
    / "src"
    / "features"
    / "auth"
    / "adapters"
    / "outbound"
    / "authorization"
    / "sqlmodel",
)


def test_no_kanban_resource_type_strings_under_auth_authorization() -> None:
    offenders: list[str] = []
    for directory in _SCANNED_DIRS:
        for path in directory.rglob("*.py"):
            text = path.read_text()
            for token in _FORBIDDEN_TOKENS:
                if token in text:
                    offenders.append(f"{path}: {token}")
    assert not offenders, (
        "Kanban-flavoured resource type strings found under "
        "src/features/auth/application/authorization/ or the SQLModel "
        "authorization adapter — these belong to whichever feature owns "
        "the resource, not auth:\n  " + "\n  ".join(offenders)
    )
