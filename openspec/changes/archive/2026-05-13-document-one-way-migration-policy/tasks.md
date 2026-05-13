## 1. Policy doc

- [x] 1.1 Add a "Migration policy" section to `docs/operations.md` covering:
  - (a) Reversible migrations are the default.
  - (b) Destructive migrations (column drops, table drops, irreversible data transforms) MUST raise `NotImplementedError` in `downgrade()` with a message pointing to `docs/operations.md#migration-policy`.
  - (c) The runbook for actually recovering from such a deploy is "restore from backup".
  - (d) The `# allow: destructive` inline-comment escape hatch and when to use it.

## 2. Apply to existing footgun

- [x] 2.1 Edit `alembic/versions/20260513_0010_drop_users_password_hash.py` (lines 34-47): replace the `op.add_column(... server_default="")` body — including the misleading comment "Restore the column with a server-side empty default so existing rows satisfy the NOT NULL constraint" — with:
  ```python
  def downgrade() -> None:
      raise NotImplementedError(
          "One-way migration: drop of users.password_hash is not safely reversible. "
          "If you need to revert, restore from backup. See docs/operations.md#migration-policy."
      )
  ```

## 3. Pytest scanner

- [x] 3.1 Implement `tests/quality/test_migration_policy.py`:
  - Walks `alembic/versions/*.py` via `ast.parse`.
  - For each file, parse the `upgrade()` function body and detect calls to destructive alembic ops: `op.drop_column`, `op.drop_table`, `op.drop_index`, plus `op.execute(<str-literal>)` where `literal.strip().upper()` starts with `DROP ` or contains `ALTER TABLE ` and a later ` DROP `. Match by attribute access (`ast.Attribute(value=ast.Name(id="op"), attr=...)`) so `import alembic.op as op` and aliased imports both work.
  - For each destructive call, look up the same line in the source via `ast.get_source_segment` (or `linecache`); if it ends with `# allow: destructive` (whitespace-tolerant), skip.
  - Otherwise, parse the `downgrade()` function body and assert its first executable statement is `raise NotImplementedError(...)`.
  - Aggregate all violations and emit one `pytest.fail` message listing each `(file, line, op)` (don't bail on the first).

## 4. Makefile + CI

- [x] 4.1 Add a `make migrations-check` target running `uv run pytest tests/quality/test_migration_policy.py -q`.
- [x] 4.2 Update the `make ci` recipe so `migrations-check` runs alongside `quality` and `cov`.

## 5. Tests for the scanner itself

Use `tmp_path` fixtures: each test writes one or more synthetic migration files to a temp directory and invokes the scanner function (extracted from `test_migration_policy.py` as `scan(directory: Path) -> list[Violation]`). The top-level `test_migration_policy` simply calls `scan(Path("alembic/versions"))` and asserts `[] == violations`.

- [x] 5.1 Unit: synthetic migration with `op.drop_column("foo", "bar")` + `raise NotImplementedError(...)` → `scan` returns `[]`.
- [x] 5.2 Unit: synthetic migration with `op.drop_column("foo", "bar")` + `pass` → `scan` returns one violation naming the file and line.
- [x] 5.3 Unit: synthetic migration with `op.drop_index("idx_foo")  # allow: destructive` + non-raising downgrade → `scan` returns `[]`.
- [x] 5.4 Unit: synthetic migration with `op.execute("DROP TABLE foo")` + non-raising downgrade → `scan` returns one violation.
- [x] 5.5 Unit: synthetic migration with `op.execute("alter table foo drop column bar")` (lower case) + non-raising downgrade → `scan` returns one violation (regex/uppercasing works).

## 6. Wrap-up

- [x] 6.1 `make ci` green (including `make migrations-check`).
