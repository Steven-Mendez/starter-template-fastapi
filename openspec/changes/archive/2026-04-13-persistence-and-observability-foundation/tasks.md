## 1. TDD Repository Contract Coverage

- [x] 1.1 Add backend-agnostic repository contract tests that run against the current in-memory implementation.
- [x] 1.2 Add failing contract fixtures for SQLite backend parity (success paths and domain errors).

## 2. Implement SQLite Repository Backend

- [x] 2.1 Add SQLite persistence module and schema/bootstrap logic for boards, columns, and cards.
- [x] 2.2 Implement repository methods to satisfy existing `KanbanRepository` contract semantics.
- [x] 2.3 Add configuration-based backend selection while keeping in-memory as a supported option.
- [x] 2.4 Make repository contract tests pass for both backends.

## 3. Observability and Operational Health

- [x] 3.1 Add failing tests for structured request logging fields and persistence readiness health responses.
- [x] 3.2 Implement request lifecycle structured logging with stable fields and request ID integration.
- [x] 3.3 Extend health endpoint to include persistence readiness status for the active backend.
- [x] 3.4 Run full non-e2e test suite and document backend/health behavior in README.
