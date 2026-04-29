from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tests.architecture.conftest import iter_python_modules, parse_module_ast

pytestmark = pytest.mark.architecture


def test_application_shared_does_not_import_domain_aggregates() -> None:
    root = Path(__file__).resolve().parents[2]
    aggregate_stems = {
        path.name
        for path in (root / "src/domain").iterdir()
        if path.is_dir() and path.name != "shared"
    }

    for path in iter_python_modules("src.application.shared"):
        tree = parse_module_ast(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                for stem in aggregate_stems:
                    assert not node.module.startswith(f"src.domain.{stem}."), (
                        f"{path} imports aggregate module {node.module}"
                    )


def test_application_declares_no_app_result_types() -> None:
    forbidden = {"App" + "Ok", "App" + "Err", "App" + "Result"}
    for path in iter_python_modules("src.application"):
        tree = parse_module_ast(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                assert node.name not in forbidden, (
                    f"{path} declares forbidden {node.name}"
                )
