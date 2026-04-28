from __future__ import annotations

from pathlib import Path

import pytest

MARKER = pytest.mark.architecture


@MARKER
def test_no_legacy_outbound_roots_under_infrastructure() -> None:
    """hexagonal-architecture-conformance: outbound adapters stay under
    adapters/outbound.
    """
    infra_root = Path(__file__).resolve().parents[2] / "src" / "infrastructure"
    banned_roots = {"persistence", "messaging", "external"}

    direct_children = {
        child.name
        for child in infra_root.iterdir()
        if child.is_dir() and not child.name.startswith("__")
    }
    assert direct_children.isdisjoint(banned_roots), (
        "hexagonal-architecture-conformance: "
        "legacy outbound roots found directly under src/infrastructure; "
        "move them under src/infrastructure/adapters/outbound/<concern>"
    )
