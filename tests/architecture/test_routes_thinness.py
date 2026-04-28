from __future__ import annotations

import ast

import pytest

from tests.architecture.conftest import iter_python_modules, parse_module_ast

MARKER = pytest.mark.architecture


def _is_route_decorator(decorator: ast.expr) -> bool:
    if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute):
        return decorator.func.attr in {"get", "post", "put", "patch", "delete"}
    return False


@MARKER
def test_route_handlers_call_exactly_one_use_case() -> None:
    """fastapi-hexagonal-architecture: Routes stay thin by invoking one use case."""
    for path in iter_python_modules("src.api.routers"):
        if path.name == "root.py":
            continue
        tree = parse_module_ast(path)
        for node in tree.body:
            if not isinstance(node, ast.FunctionDef):
                continue
            if not any(_is_route_decorator(dec) for dec in node.decorator_list):
                continue
            use_case_calls = 0
            for child in ast.walk(node):
                if isinstance(child, ast.Call) and isinstance(
                    child.func, ast.Attribute
                ):
                    if child.func.attr == "execute":
                        use_case_calls += 1
            assert use_case_calls == 1, (
                "fastapi-hexagonal-architecture: "
                f"route {node.name} in {path} must call exactly one "
                "*UseCase.execute(...)"
            )


@MARKER
def test_routes_do_not_import_infrastructure() -> None:
    """fastapi-hexagonal-architecture: Routes must not import infrastructure
    directly.
    """
    for path in iter_python_modules("src.api.routers"):
        tree = parse_module_ast(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("src.infrastructure"), (
                        "fastapi-hexagonal-architecture: "
                        f"route module {path} imports forbidden module {alias.name}"
                    )
            if isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.startswith("src.infrastructure"), (
                    "fastapi-hexagonal-architecture: "
                    f"route module {path} imports forbidden module {node.module}"
                )
