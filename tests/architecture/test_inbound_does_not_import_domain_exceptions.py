from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tests.architecture.conftest import iter_python_modules, parse_module_ast

MARKER = pytest.mark.architecture


def _domain_exception_names() -> set[str]:
    module = Path(__file__).resolve().parents[2] / "src/domain/kanban/errors.py"
    tree = parse_module_ast(module)
    return {node.name for node in tree.body if isinstance(node, ast.ClassDef)}


@MARKER
def test_api_does_not_import_domain_exceptions() -> None:
    (
        """hexagonal-architecture-conformance: """
        """check-inbound-not-import-domain-exceptions."""
    )
    exception_names = _domain_exception_names()
    for path in iter_python_modules("src.api"):
        tree = parse_module_ast(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                is_domain_exceptions_module = module.endswith(
                    "domain.kanban." + "exceptions"
                )
                imported_names = {alias.name for alias in node.names}
                has_exception_name = bool(imported_names & exception_names)
                assert not (is_domain_exceptions_module or has_exception_name), (
                    "hexagonal-architecture-conformance: "
                    f"api module {path} imports domain exception symbols"
                )
