"""Static check: authorization never mentions any feature's vocabulary.

After ``decouple-authz-from-features``, the authorization engine learns
about resource types only from the runtime registry. This test fails if
a future change re-introduces a feature-flavoured resource type string
(``"thing"``, ``"column"``, ``"card"``, ``"board"``, …) under
``authorization/application/`` or its SQLModel adapter.
"""

from __future__ import annotations

import pathlib

import pytest

pytestmark = pytest.mark.unit

_FORBIDDEN_TOKENS = (
    '"thing"',
    '"column"',
    '"card"',
    '"board"',
    '"kanban"',
)
_PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[5]
_SCANNED_DIRS = (
    _PROJECT_ROOT / "src" / "features" / "authorization" / "application",
    _PROJECT_ROOT
    / "src"
    / "features"
    / "authorization"
    / "adapters"
    / "outbound"
    / "sqlmodel",
)


def test_no_feature_resource_type_strings_under_authorization() -> None:
    offenders: list[str] = []
    for directory in _SCANNED_DIRS:
        for path in directory.rglob("*.py"):
            text = path.read_text()
            for token in _FORBIDDEN_TOKENS:
                if token in text:
                    offenders.append(f"{path}: {token}")
    assert not offenders, (
        "Feature-flavoured resource type strings found under the "
        "authorization feature — these belong to whichever feature owns "
        "the resource type, not authorization itself:\n  " + "\n  ".join(offenders)
    )
