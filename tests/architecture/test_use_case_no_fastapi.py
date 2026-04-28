from __future__ import annotations

import ast

import pytest

from tests.architecture.conftest import iter_python_modules, parse_module_ast

MARKER = pytest.mark.architecture


@MARKER
def test_use_cases_do_not_import_frameworks_or_infra() -> None:
    """hexagonal-architecture-conformance: check-use-case-no-fastapi."""
    forbidden_prefixes = (
        "fastapi",
        "starlette",
        "sqlmodel",
        "sqlalchemy",
        "httpx",
        "src.infrastructure",
    )
    for path in iter_python_modules("src.application.use_cases"):
        tree = parse_module_ast(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith(forbidden_prefixes), (
                        "hexagonal-architecture-conformance: "
                        f"use-case purity violated in {path}: import {alias.name}"
                    )
            if isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.startswith(forbidden_prefixes), (
                    "hexagonal-architecture-conformance: "
                    f"use-case purity violated in {path}: from {node.module} import ..."
                )
