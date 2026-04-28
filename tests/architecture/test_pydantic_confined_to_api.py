from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tests.architecture.conftest import parse_module_ast

MARKER = pytest.mark.architecture


def _all_python_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*.py") if path.name != "__init__.py")


def _inherits_pydantic_model(node: ast.ClassDef) -> bool:
    for base in node.bases:
        if isinstance(base, ast.Name) and base.id in {"BaseModel", "RootModel"}:
            return True
        if isinstance(base, ast.Attribute) and base.attr in {"BaseModel", "RootModel"}:
            return True
    return False


@MARKER
def test_pydantic_models_confined_to_api_layer() -> None:
    """fastapi-hexagonal-architecture: check-pydantic-confined-to-api."""
    root = Path(__file__).resolve().parents[2] / "src"
    for path in _all_python_files(root):
        rel = path.relative_to(root)
        if rel.parts and rel.parts[0] == "api":
            continue
        tree = parse_module_ast(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and _inherits_pydantic_model(node):
                raise AssertionError(
                    "fastapi-hexagonal-architecture: "
                    f"pydantic model {node.name} must be confined "
                    f"to src/api, found in {path}"
                )
