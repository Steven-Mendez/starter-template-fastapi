from __future__ import annotations

import ast

import pytest

from tests.architecture.conftest import iter_python_modules, parse_module_ast

pytestmark = pytest.mark.architecture


def test_use_case_execute_methods_are_not_handle_passthroughs() -> None:
    violations: list[str] = []
    for path in iter_python_modules("src.application.use_cases"):
        tree = parse_module_ast(path)
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef) or not node.name.endswith("UseCase"):
                continue
            for member in node.body:
                if not isinstance(member, ast.FunctionDef) or member.name != "execute":
                    continue
                if len(member.body) != 1:
                    continue
                only_stmt = member.body[0]
                if not isinstance(only_stmt, ast.Return):
                    continue
                call = only_stmt.value
                if isinstance(call, ast.Call) and isinstance(call.func, ast.Name):
                    if call.func.id.startswith("handle_"):
                        violations.append(
                            f"{path}:{member.lineno} returns passthrough {call.func.id}"
                        )

    assert not violations, "\n".join(violations)


def test_commands_and_queries_define_no_handle_functions() -> None:
    violations: list[str] = []
    for package in ("src.application.commands", "src.application.queries"):
        for path in iter_python_modules(package):
            tree = parse_module_ast(path)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name.startswith(
                    "handle_"
                ):
                    violations.append(f"{path}:{node.lineno} defines {node.name}")

    assert not violations, "\n".join(violations)
