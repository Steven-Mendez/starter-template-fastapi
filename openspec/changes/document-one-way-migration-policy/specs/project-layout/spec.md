## ADDED Requirements

### Requirement: Destructive migrations raise on downgrade and are scanned in CI

Migrations whose `upgrade()` performs destructive operations (column drops, table drops, index drops, or `op.execute` running a `DROP` / `ALTER TABLE ... DROP`) SHALL have a `downgrade()` whose first executable statement is `raise NotImplementedError("...")` and whose message references `docs/operations.md#migration-policy`. Narrowing `alter_column` (e.g., `String(length=255)` → `String(length=64)`) is destructive but cannot be detected statically; operators MUST opt in by hand to the same convention.

The policy SHALL be documented in `docs/operations.md`. The project SHALL ship a `make migrations-check` pytest scanner that walks `alembic/versions/*.py` and fails when a destructive operation is found without either a raising `downgrade()` or an inline `# allow: destructive` comment **on the same line as the destructive call**. `make ci` SHALL invoke `make migrations-check`.

#### Scenario: Existing column-drop migration refuses to downgrade

- **GIVEN** the migration `20260513_0010_drop_users_password_hash`
- **WHEN** an operator runs `alembic downgrade -1`
- **THEN** the operation raises `NotImplementedError`
- **AND** the error message references `docs/operations.md#migration-policy`

#### Scenario: Scanner accepts a compliant destructive migration

- **GIVEN** a migration whose `upgrade()` calls `op.drop_column("foo", "bar")` and whose `downgrade()` body is `raise NotImplementedError("...")`
- **WHEN** `make migrations-check` runs
- **THEN** the command exits 0

#### Scenario: Scanner rejects a non-compliant destructive migration

- **GIVEN** a migration whose `upgrade()` calls `op.drop_column("foo", "bar")` and whose `downgrade()` body is `pass`
- **WHEN** `make migrations-check` runs
- **THEN** the command exits non-zero
- **AND** the failure message names the offending file and line

#### Scenario: Scanner respects the inline override

- **GIVEN** a migration whose `upgrade()` contains `op.drop_index("idx_foo")  # allow: destructive` and whose `downgrade()` recreates the index normally
- **WHEN** `make migrations-check` runs
- **THEN** the command exits 0

#### Scenario: Scanner detects raw-SQL drops

- **GIVEN** a migration whose `upgrade()` calls `op.execute("DROP TABLE foo")` and whose `downgrade()` body is `pass`
- **WHEN** `make migrations-check` runs
- **THEN** the command exits non-zero

#### Scenario: CI gate enforces the policy

- **WHEN** a developer opens a PR adding a non-compliant destructive migration
- **THEN** `make ci` fails on the `migrations-check` step
- **AND** the failure surfaces in the GitHub Actions logs before any deploy

#### Scenario: Irreversible migration attempted downgrade aborts loudly

- **GIVEN** a destructive migration whose `downgrade()` raises `NotImplementedError("... see docs/operations.md#migration-policy")`
- **WHEN** an operator runs `uv run alembic downgrade -1` against that revision
- **THEN** the command aborts with a `NotImplementedError` whose message references `docs/operations.md#migration-policy`
- **AND** no schema change is applied (the prior `upgrade` state remains)
- **AND** no data is silently re-introduced under a default value
