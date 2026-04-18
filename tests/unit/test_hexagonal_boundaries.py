from __future__ import annotations

import ast
import inspect
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Set

import pytest
from fastapi.routing import APIRoute

from src.api.kanban_router import kanban_router

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "src"


@dataclass
class ImportDiagnostic:
    source_module: str
    target_import: str
    violated_rule: str

    def __str__(self) -> str:
        return f"{self.source_module} imports {self.target_import} (Violation: {self.violated_rule})"


def parse_imports(file_path: Path) -> Set[str]:
    content = file_path.read_text(encoding="utf-8")
    tree = ast.parse(content, filename=str(file_path))
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module)
    return imports


def get_module_imports() -> Dict[str, Set[str]]:
    modules = {}
    for py_file in SRC_DIR.rglob("*.py"):
        if py_file.name == "__init__.py" and py_file.stat().st_size == 0:
            continue
        rel_path = py_file.relative_to(ROOT)
        module_name = str(rel_path.with_suffix("")).replace("/", ".")
        modules[module_name] = parse_imports(py_file)
    return modules


def get_layer(module_name: str) -> str:
    if module_name.startswith("src.domain"):
        return "domain"
    if module_name.startswith("src.application"):
        return "application"
    if module_name.startswith("src.api"):
        return "api"
    if module_name.startswith("src.infrastructure"):
        return "infrastructure"
    return "other"


DENY_MATRIX = {
    "domain": [
        "src.application",
        "src.api",
        "src.infrastructure",
        "fastapi",
        "sqlmodel",
        "sqlalchemy",
        "settings",
        "src.settings",
    ],
    "application": [
        "src.api",
        "src.infrastructure",
        "fastapi",
        "sqlmodel",
        "sqlalchemy",
        "settings",
        "src.settings",
    ],
    "api": [
        "src.infrastructure",
    ],
    "infrastructure": [
        "src.api",
    ],
}


def check_architecture() -> List[ImportDiagnostic]:
    modules = get_module_imports()
    diagnostics = []

    for module_name, imports in modules.items():
        layer = get_layer(module_name)
        if layer == "other":
            continue

        denied_prefixes = DENY_MATRIX.get(layer, [])
        for imp in imports:
            for denied in denied_prefixes:
                if imp == denied or imp.startswith(f"{denied}."):
                    diagnostics.append(
                        ImportDiagnostic(
                            source_module=module_name,
                            target_import=imp,
                            violated_rule=f"Layer '{layer}' cannot import '{denied}'"
                        )
                    )
    return diagnostics


def test_hexagonal_architecture_boundaries() -> None:
    diagnostics = check_architecture()
    if diagnostics:
        error_msgs = "\n".join(f" - {d}" for d in diagnostics)
        pytest.fail(f"Architecture boundary violations detected:\n{error_msgs}")


def test_api_routes_use_cqrs_handlers() -> None:
    for route in kanban_router.routes:
        if not isinstance(route, APIRoute):
            continue

        endpoint = route.endpoint
        sig = inspect.signature(endpoint)

        has_query_handler = False
        has_command_handler = False
        has_repository = False

        for param_name, param in sig.parameters.items():
            param_str = str(param.annotation)
            if "KanbanQueryHandlers" in param_str:
                has_query_handler = True
            if "KanbanCommandHandlers" in param_str:
                has_command_handler = True
            if "Repository" in param_str or "repository" in param_name.lower():
                has_repository = True

        assert not has_repository, f"Endpoint {endpoint.__name__} must not depend on a repository directly."

        methods = route.methods or set()

        if "GET" in methods:
            assert has_query_handler, f"Read endpoint {endpoint.__name__} must use KanbanQueryHandlers."
            assert not has_command_handler, f"Read endpoint {endpoint.__name__} must not use KanbanCommandHandlers."
        else:
            assert has_command_handler, f"Write endpoint {endpoint.__name__} must use KanbanCommandHandlers."
            assert not has_query_handler, f"Write endpoint {endpoint.__name__} must not use KanbanQueryHandlers."
