## 1. TDD Lifecycle Coverage

- [x] 1.1 Add failing unit tests for SQLite repository close idempotency and context-manager cleanup.
- [x] 1.2 Add failing fixture-level tests/coverage that enforce repository cleanup in test lifecycles.

## 2. Implement Lifecycle Management

- [x] 2.1 Implement `close()` and context manager support in `SQLiteKanbanRepository`.
- [x] 2.2 Ensure application lifecycle teardown closes close-capable repositories.
- [x] 2.3 Update repository-producing tests/fixtures to close created SQLite repositories.

## 3. Validate and Finalize

- [x] 3.1 Run lint, typecheck, non-e2e, e2e, and coverage checks; verify no unclosed-connection warnings.
