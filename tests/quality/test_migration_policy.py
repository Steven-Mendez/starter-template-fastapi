"""Enforce the project migration policy at PR time.

A migration is *destructive* when its ``upgrade()`` drops a column, drops a
table, drops an index, or runs raw SQL (``op.execute``) whose first non-whitespace
keyword is ``DROP`` or whose ``ALTER TABLE`` clause contains a later ``DROP``.
Destructive migrations MUST have a ``downgrade()`` whose first executable
statement raises ``NotImplementedError``. Operators can opt out of the policy
on a per-call basis by appending ``# allow: destructive`` to the destructive
line — see ``docs/operations.md#migration-policy``.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

DESTRUCTIVE_OP_ATTRS: frozenset[str] = frozenset(
    {"drop_column", "drop_table", "drop_index"}
)
ALLOW_PATTERN = re.compile(r"#\s*allow:\s*destructive\b")
# Matches ALTER TABLE ... DROP (column/constraint/etc.) across word breaks.
ALTER_TABLE_DROP = re.compile(r"\bALTER\s+TABLE\b.*\bDROP\b", re.DOTALL)


@dataclass(frozen=True, slots=True)
class Violation:
    path: Path
    line: int
    op: str

    def render(self) -> str:
        return (
            f"{self.path}:{self.line} — destructive `{self.op}` "
            "without raising downgrade()"
        )


def _is_op_call(node: ast.AST, attr_in: frozenset[str] | set[str]) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "op"
        and node.func.attr in attr_in
    )


def _execute_drops_payload(call: ast.Call) -> bool:
    """Return True when ``op.execute(<str-literal>)`` runs a DROP/ALTER-DROP."""
    if not call.args:
        return False
    arg = call.args[0]
    literal: str | None = None
    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
        literal = arg.value
    elif (
        isinstance(arg, ast.Call)
        and isinstance(arg.func, ast.Attribute)
        and arg.func.attr == "text"
        and arg.args
        and isinstance(arg.args[0], ast.Constant)
        and isinstance(arg.args[0].value, str)
    ):
        literal = arg.args[0].value
    if literal is None:
        return False
    text = literal.strip().upper()
    if text.startswith("DROP "):
        return True
    return bool(ALTER_TABLE_DROP.search(text))


def _function(tree: ast.Module, name: str) -> ast.FunctionDef | None:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def _downgrade_raises_not_implemented(downgrade: ast.FunctionDef | None) -> bool:
    if downgrade is None or not downgrade.body:
        return False
    first = downgrade.body[0]
    # Skip a leading docstring expression so a one-line docstring doesn't
    # block the policy.
    if (
        isinstance(first, ast.Expr)
        and isinstance(first.value, ast.Constant)
        and isinstance(first.value.value, str)
        and len(downgrade.body) >= 2
    ):
        first = downgrade.body[1]
    if not isinstance(first, ast.Raise) or first.exc is None:
        return False
    exc = first.exc
    if isinstance(exc, ast.Call):
        exc = exc.func
    if isinstance(exc, ast.Name):
        return exc.id == "NotImplementedError"
    if isinstance(exc, ast.Attribute):
        return exc.attr == "NotImplementedError"
    return False


def _line_has_allow_comment(source_lines: list[str], lineno: int) -> bool:
    if not 1 <= lineno <= len(source_lines):
        return False
    return bool(ALLOW_PATTERN.search(source_lines[lineno - 1]))


def _destructive_calls_in(upgrade: ast.FunctionDef) -> list[tuple[str, int]]:
    found: list[tuple[str, int]] = []
    for sub in ast.walk(upgrade):
        if not isinstance(sub, ast.Call):
            continue
        if _is_op_call(sub, DESTRUCTIVE_OP_ATTRS):
            assert isinstance(sub.func, ast.Attribute)
            found.append((sub.func.attr, sub.lineno))
        elif _is_op_call(sub, {"execute"}) and _execute_drops_payload(sub):
            found.append(("execute", sub.lineno))
    return found


def scan(directory: Path) -> list[Violation]:
    """Walk ``directory`` for Alembic migrations and return policy violations."""
    violations: list[Violation] = []
    for path in sorted(directory.glob("*.py")):
        if path.name == "__init__.py":
            continue
        source = path.read_text()
        source_lines = source.splitlines()
        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError:
            continue
        upgrade = _function(tree, "upgrade")
        if upgrade is None:
            continue
        destructive = _destructive_calls_in(upgrade)
        if not destructive:
            continue
        downgrade = _function(tree, "downgrade")
        raises = _downgrade_raises_not_implemented(downgrade)
        for op_name, lineno in destructive:
            if _line_has_allow_comment(source_lines, lineno):
                continue
            if raises:
                continue
            violations.append(Violation(path=path, line=lineno, op=op_name))
    return violations


def test_migration_policy() -> None:
    """Real migrations under ``alembic/versions`` comply with the policy."""
    repo_root = Path(__file__).resolve().parents[2]
    violations = scan(repo_root / "alembic" / "versions")
    if violations:
        rendered = "\n".join(v.render() for v in violations)
        raise AssertionError(
            "Destructive migrations missing raising downgrade() — "
            "see docs/operations.md#migration-policy:\n" + rendered
        )


def _write(path: Path, body: str) -> Path:
    path.write_text(body)
    return path


def test_scan_accepts_drop_column_with_raising_downgrade(tmp_path: Path) -> None:
    _write(
        tmp_path / "0001_drop_column.py",
        """
from alembic import op


def upgrade() -> None:
    op.drop_column("foo", "bar")


def downgrade() -> None:
    raise NotImplementedError("one-way; see docs/operations.md#migration-policy")
""",
    )
    assert scan(tmp_path) == []


def test_scan_rejects_drop_column_with_pass_downgrade(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "0002_drop_column.py",
        """
from alembic import op


def upgrade() -> None:
    op.drop_column("foo", "bar")


def downgrade() -> None:
    pass
""",
    )
    violations = scan(tmp_path)
    assert len(violations) == 1
    assert violations[0].path == path
    assert violations[0].op == "drop_column"
    # ``op.drop_column`` is on line 6 of the synthetic source above.
    assert violations[0].line == 6


def test_scan_respects_allow_destructive_comment(tmp_path: Path) -> None:
    _write(
        tmp_path / "0003_drop_index_allowed.py",
        """
from alembic import op


def upgrade() -> None:
    op.drop_index("idx_foo")  # allow: destructive


def downgrade() -> None:
    op.create_index("idx_foo", "foo", ["x"])
""",
    )
    assert scan(tmp_path) == []


def test_scan_detects_raw_sql_drop_table(tmp_path: Path) -> None:
    _write(
        tmp_path / "0004_execute_drop.py",
        """
from alembic import op


def upgrade() -> None:
    op.execute("DROP TABLE foo")


def downgrade() -> None:
    pass
""",
    )
    violations = scan(tmp_path)
    assert len(violations) == 1
    assert violations[0].op == "execute"


def test_scan_detects_lowercase_alter_table_drop_column(tmp_path: Path) -> None:
    _write(
        tmp_path / "0005_execute_alter_drop.py",
        """
from alembic import op


def upgrade() -> None:
    op.execute("alter table foo drop column bar")


def downgrade() -> None:
    pass
""",
    )
    violations = scan(tmp_path)
    assert len(violations) == 1
    assert violations[0].op == "execute"
