## Context

A misleading `downgrade()` is worse than no downgrade. The right answer is to raise explicitly and point at the runbook. A documented policy alone leaks at the boundary — the next developer who writes `op.drop_column` won't re-read `docs/operations.md`. An automated check catches the slip before merge.

## Decisions

- **`raise NotImplementedError` over a comment**: enforced at runtime, not just at code-review time. If an operator runs `alembic downgrade` against a destructive migration in production, the operation aborts loudly with a pointer to the runbook.
- **Include the pytest scanner** (the previously-optional task). The scanner is cheap (~30 lines of AST walking) and the failure mode it catches (silent corruption on downgrade) is severe. The scanner:
  - Walks every `alembic/versions/*.py`.
  - Detects, in the `upgrade()` function body, calls to destructive alembic ops:
    - `op.drop_column(...)`, `op.drop_table(...)`, `op.drop_index(...)`.
    - `op.execute(<str-literal>)` where the literal, after `.strip().upper()`, begins with `DROP ` or contains `ALTER TABLE ` followed (anywhere later) by ` DROP `.
  - For each destructive op without an inline `# allow: destructive` comment **on the same line** (using `ast.get_source_segment` + line lookup), asserts that the file's `downgrade()` function has `raise NotImplementedError(...)` as its first executable statement.
  - Out of scope: narrowing `op.alter_column` (cannot be detected reliably from AST without resolving runtime types). Operators must apply the `# allow: destructive` opt-out — and accompanying raising downgrade — by hand for those.
- **`make migrations-check`** is the new target. `make ci` depends on it. CI is the only place this matters in practice.
- **Escape hatch**: an inline `# allow: destructive` comment on the destructive line lets a developer opt out for a known-reversible case (e.g., dropping an index that's already been created on a hot replica). PR review enforces the comment.

## Non-goals

- Not a zero-downtime migration framework. We make destructive migrations refuse to silently corrupt data; we do not prescribe expand/contract patterns or background-fill orchestration.
- Not a generalized "data migration vs schema migration" separation. The policy lives at the alembic-op level; data-migration safety is a separate review concern.
- Not a runtime backup tool. The recovery story for a destructive deploy is "restore from backup" — this change documents the policy but does not ship a snapshot/restore script.
- Not a catch-all linter for narrowing `alter_column` calls. Operators must opt in by hand (see Decisions).

## Risks / Trade-offs

- **Risk**: false positives on `op.drop_index` where the index can safely be re-created. Mitigation: the `# allow: destructive` comment is a one-token override.
- **Risk**: the scanner doesn't understand all alembic patterns (e.g., raw SQL inside `op.execute`). Mitigation: the scanner detects `op.execute` with a string starting with `DROP ` / `ALTER TABLE ... DROP ` and applies the same rule.

## Migration

Single PR. Backwards compatible — the change makes a previously-broken downgrade refuse rather than corrupt.
