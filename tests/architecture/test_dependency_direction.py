from __future__ import annotations

import ast

import pytest

from tests.architecture.conftest import iter_python_modules, parse_module_ast

MARKER = pytest.mark.architecture


@MARKER
def test_domain_has_no_outward_or_framework_imports() -> None:
    (
        """hexagonal-architecture-conformance: """
        """Domain models should not depend on frameworks."""
    )
    forbidden_prefixes = (
        "src.application",
        "src.api",
        "src.infrastructure",
        "fastapi",
        "starlette",
        "sqlmodel",
        "sqlalchemy",
        "httpx",
        "pydantic",
    )
    for path in iter_python_modules("src.domain"):
        tree = parse_module_ast(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith(forbidden_prefixes), (
                        "hexagonal-architecture-conformance: "
                        f"domain purity violated in {path}: import {alias.name}"
                    )
            if isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.startswith(forbidden_prefixes), (
                    "hexagonal-architecture-conformance: "
                    f"domain purity violated in {path}: from {node.module} import ..."
                )


@MARKER
def test_application_has_no_transport_or_infrastructure_imports() -> None:
    """hexagonal-architecture-conformance: Application layer must stay
    framework-agnostic.
    """
    forbidden_prefixes = (
        "src.api",
        "src.infrastructure",
        "fastapi",
        "starlette",
        "sqlmodel",
        "sqlalchemy",
        "httpx",
    )
    for path in iter_python_modules("src.application"):
        tree = parse_module_ast(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith(forbidden_prefixes), (
                        "hexagonal-architecture-conformance: "
                        f"application purity violated in {path}: import {alias.name}"
                    )
            if isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.startswith(forbidden_prefixes), (
                    "hexagonal-architecture-conformance: "
                    "application purity violated in "
                    f"{path}: from {node.module} import ..."
                )
