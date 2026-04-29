from __future__ import annotations

import ast

import pytest

from tests.architecture.conftest import iter_python_modules, parse_module_ast

pytestmark = pytest.mark.architecture


def _base_name(base: ast.expr) -> str | None:
    if isinstance(base, ast.Name):
        return base.id
    if isinstance(base, ast.Attribute):
        return base.attr
    return None


def test_application_ports_do_not_aggregate_repository_ports() -> None:
    violations: list[str] = []

    for path in iter_python_modules("src.application.ports"):
        tree = parse_module_ast(path)
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue

            base_names = [name for base in node.bases if (name := _base_name(base))]
            if "Protocol" not in base_names:
                continue

            repository_bases = [
                name for name in base_names if name.endswith("RepositoryPort")
            ]
            if len(repository_bases) > 1:
                joined_bases = ", ".join(repository_bases)
                violations.append(
                    f"{path}: protocol {node.name} aggregates {joined_bases}"
                )

    assert not violations, "\n".join(violations)
