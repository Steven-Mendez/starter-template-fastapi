## Why

`alembic/versions/20260513_0010_drop_users_password_hash.py:34-47` drops `users.password_hash` in `upgrade()`, then `downgrade()` re-adds the column with `server_default=""` — so a downgrade in production would silently mark every account as having an empty password. The downgrade is a footgun.

The wider issue: there is no documented policy for migrations whose downgrade cannot be honestly implemented, and no automated check that catches the next misleading downgrade.

## What Changes

- Add a project-wide convention to `docs/operations.md` ("Migration policy" section): migrations that drop columns or otherwise lose data MUST mark their `downgrade()` as `raise NotImplementedError("one-way migration; see docs/operations.md#migration-policy")`.
- Apply the convention retroactively to `alembic/versions/20260513_0010_drop_users_password_hash.py`: replace the misleading `downgrade()` body with the `raise NotImplementedError(...)`.
- **Include the pytest scanner.** Add `make migrations-check` that runs a pytest scanning `alembic/versions/*.py` for destructive operations and asserts each one has either `raise NotImplementedError` in its `downgrade()` or a `# allow: destructive` comment on the destructive line. Wire `make migrations-check` into `make ci`. Rationale: cheap to add (~30 lines of AST scanning), catches the next `op.drop_column` without policy compliance at PR time rather than at deploy time.
- Document the runbook section: what an operator does if they truly need to roll back a destructive migration (typically "restore from backup").

**Capabilities — Modified**: `quality-automation` (CI rule) and `project-layout` (policy doc).

## Impact

- **Code**:
  - `alembic/versions/20260513_0010_drop_users_password_hash.py` (replace `downgrade()` body).
  - `tests/quality/test_migration_policy.py` (new — AST scanner).
  - `Makefile` (new `migrations-check` target; `ci` depends on it).
  - `docs/operations.md` (new "Migration policy" section).
- **Production**: prevents accidental downgrade from corrupting auth data; future migrations can't merge without compliance.

## Depends on / Conflicts with

- **Depends on**: none.
- **Blocks (informational)**: every change that adds an alembic migration MUST follow this policy. In particular: `add-gdpr-erasure-and-export` (new `users.is_erased` column), `fix-outbox-dispatch-idempotency` (new `processed_outbox_messages` table), `improve-db-performance` (new `ix_users_created_at` index — non-destructive, but the policy still applies in spirit), `add-outbox-retention-prune` (no migration but the prune semantics interact). Each of those changes' tasks list explicitly references `make migrations-check`.
- **Conflicts with**: none directly. `Makefile` is shared with `add-outbox-retention-prune`, `speed-up-ci`, `add-worker-image-target` — section-level edits.
