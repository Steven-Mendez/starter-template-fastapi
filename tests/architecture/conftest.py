from __future__ import annotations

import ast
from pathlib import Path
from typing import Iterator


def iter_python_modules(package_name: str) -> Iterator[Path]:
    root = Path(__file__).resolve().parents[2]
    package_path = root / package_name.replace(".", "/")
    for path in sorted(package_path.rglob("*.py")):
        if path.name == "__init__.py":
            continue
        yield path


def parse_module_ast(path: Path) -> ast.Module:
    source = path.read_text(encoding="utf-8")
    return ast.parse(source, filename=str(path))
