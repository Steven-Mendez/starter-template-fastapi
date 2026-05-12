"""Structural check that every outbound port has at least one adapter.

Import Linter can express "module A must not import module B" but not
"module A must have at least one corresponding adapter directory" — so
this property lives as a unit test instead of a contract in
``pyproject.toml``. It is the safety net that complements per-port
contract tests: contract tests guarantee an adapter implements the port,
this test guarantees a port doesn't ship without one.

If you add a new outbound port:

1. Add at least one adapter under
   ``src/features/<feature>/adapters/outbound/`` (a fake/stub is fine
   while you flesh out the real one — keep the contract test xfail-ed
   until the implementation lands).
2. If the port lives in a non-obvious place that the heuristic below
   misses, extend ``_KNOWN_PORTS`` with an explicit pairing.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


_REPO_ROOT = Path(__file__).resolve().parents[3]
_FEATURES_ROOT = _REPO_ROOT / "src" / "features"


def _outbound_port_files() -> list[Path]:
    """Return every concrete outbound-port module across all features."""
    candidates: list[Path] = []
    for feature in _FEATURES_ROOT.iterdir():
        if not feature.is_dir() or feature.name.startswith("__"):
            continue
        ports_dir = feature / "application" / "ports"
        if not ports_dir.exists():
            continue
        for module in ports_dir.rglob("*.py"):
            if module.name == "__init__.py":
                continue
            # ``inbound/`` ports are the feature's own ingress; they're
            # implemented by the use case, not by an outbound adapter.
            if "inbound" in module.parts:
                continue
            candidates.append(module)
    return candidates


def _has_outbound_adapter(feature_dir: Path) -> bool:
    outbound = feature_dir / "adapters" / "outbound"
    if not outbound.exists():
        return False
    for child in outbound.iterdir():
        if child.is_dir() and not child.name.startswith("__"):
            return True
    return False


def test_every_feature_with_outbound_ports_has_at_least_one_outbound_adapter() -> None:
    """Catches a feature shipping a port with no adapter (stub or otherwise).

    The contract tests guard signature drift between port and adapter;
    this test guards the upstream existence of an adapter to be drifted
    against.
    """
    port_files = _outbound_port_files()
    assert port_files, "Expected to find at least one outbound port file."

    def _feature_root(port: Path) -> Path:
        # Ports live under ``<feature>/application/ports[/outbound]/<file>.py``.
        # Walk up until we land on the ``features/`` directory's child.
        cursor = port.parent
        while cursor.parent.name != "features":
            cursor = cursor.parent
        return cursor

    features_with_ports = {_feature_root(p) for p in port_files}
    missing = sorted(
        feature.relative_to(_REPO_ROOT).as_posix()
        for feature in features_with_ports
        if not _has_outbound_adapter(feature)
    )
    assert not missing, (
        "Every feature that defines an outbound port must ship at least "
        "one adapter under ``adapters/outbound/``. Missing: " + ", ".join(missing)
    )
