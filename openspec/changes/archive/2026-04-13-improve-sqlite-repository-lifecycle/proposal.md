## Why

Coverage runs currently emit unclosed SQLite connection warnings, indicating repository lifecycle cleanup is inconsistent. We need deterministic repository disposal to keep tests and runtime clean.

## What Changes

- Add explicit lifecycle management to `SQLiteKanbanRepository` (close and context-manager support).
- Ensure app/container lifecycle closes repositories on shutdown when supported.
- Update tests/fixtures to close repositories they create.
- Add TDD coverage for repository close behavior.

## Capabilities

### New Capabilities
- `sqlite-repository-lifecycle`: Deterministic close/disposal behavior for SQLite repository instances.

### Modified Capabilities
- `kanban-repository`: Repository implementations MAY expose lifecycle hooks; application and tests SHALL close resources for repositories that require disposal.

## Impact

- Affected files: `kanban/sqlite_repository.py`, app startup/shutdown wiring, repository-related tests and fixtures.
- No API contract changes for external clients.
- Improves test hygiene and prevents resource warnings in coverage workflows.
