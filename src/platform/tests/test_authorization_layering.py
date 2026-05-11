"""Belt-and-braces layering test.

Walks the AST of every production module in ``src/features/{auth,authorization,kanban}``
and asserts no cross-feature imports outside the allowed seams. Import
Linter is the primary check; this test pins down the spec scenario
("Auth/Authorization/Kanban do not import each other") as Python so a
broken contract shows up in pytest output alongside the other suites.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

pytestmark = pytest.mark.unit

_PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[3]
_SRC = _PROJECT_ROOT / "src"


def _iter_feature_source_files(feature: str) -> list[pathlib.Path]:
    base = _SRC / "features" / feature
    out: list[pathlib.Path] = []
    for sub in ("application", "adapters", "composition", "domain"):
        out.extend((base / sub).rglob("*.py"))
    # Include the package's __init__.py so re-exports are scanned.
    init = base / "__init__.py"
    if init.exists():
        out.append(init)
    return out


def _imported_modules(path: pathlib.Path) -> list[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                # ImportFrom can have None for relative imports; we only
                # check absolute imports here (the project uses them
                # exclusively).
                names.append(node.module)
    return names


_FORBIDDEN = {
    "auth": ("src.features.authorization", "src.features.kanban"),
    "authorization": ("src.features.auth", "src.features.kanban"),
    "kanban": ("src.features.auth",),
}


@pytest.mark.parametrize("feature", sorted(_FORBIDDEN))
def test_feature_does_not_import_other_features(feature: str) -> None:
    forbidden_prefixes = _FORBIDDEN[feature]
    offenders: list[str] = []
    for path in _iter_feature_source_files(feature):
        for imported in _imported_modules(path):
            for forbidden in forbidden_prefixes:
                if imported == forbidden or imported.startswith(forbidden + "."):
                    offenders.append(f"{path}: {imported}")
    assert not offenders, (
        f"`{feature}` source code imports from a forbidden peer feature. "
        "Production code must communicate through ports only:\n  "
        + "\n  ".join(offenders)
    )
