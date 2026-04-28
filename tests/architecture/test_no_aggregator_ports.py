from __future__ import annotations

import ast

import pytest

from tests.architecture.conftest import iter_python_modules, parse_module_ast

MARKER = pytest.mark.architecture
FORBIDDEN_SYMBOLS = {
    "KanbanCommandInputPort",
    "KanbanQueryInputPort",
    "KanbanCommandHandlers",
    "KanbanQueryHandlers",
}


@MARKER
def test_no_protocol_aggregates_handle_methods() -> None:
    """fastapi-hexagonal-architecture: check-no-aggregator-ports."""
    for path in iter_python_modules("src.application"):
        tree = parse_module_ast(path)
        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            is_protocol = any(
                (isinstance(base, ast.Name) and base.id == "Protocol")
                or (isinstance(base, ast.Attribute) and base.attr == "Protocol")
                for base in node.bases
            )
            if not is_protocol:
                continue
            nouns: set[str] = set()
            for member in node.body:
                if isinstance(member, ast.FunctionDef) and member.name.startswith(
                    "handle_"
                ):
                    parts = member.name.split("_", 2)
                    if len(parts) >= 3:
                        nouns.add(parts[2])
            assert len(nouns) < 2, (
                "fastapi-hexagonal-architecture: "
                f"protocol {node.name} in {path} aggregates multiple handle_* nouns"
            )


@MARKER
def test_forbidden_aggregator_symbols_absent() -> None:
    """fastapi-hexagonal-architecture: check-no-aggregator-symbols."""
    for path in iter_python_modules("src.application"):
        tree = parse_module_ast(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                assert node.name not in FORBIDDEN_SYMBOLS, (
                    "fastapi-hexagonal-architecture: "
                    f"forbidden symbol {node.name} declared in {path}"
                )
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    assert alias.name not in FORBIDDEN_SYMBOLS, (
                        "fastapi-hexagonal-architecture: "
                        f"forbidden symbol {alias.name} imported in {path}"
                    )
