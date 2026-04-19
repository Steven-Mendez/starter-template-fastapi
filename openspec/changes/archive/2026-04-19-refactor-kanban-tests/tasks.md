## 1. Shared test setup

- [x] 1.1 Add reusable Kanban fixtures/builders for board and card creation.
- [x] 1.2 Migrate existing Kanban tests to shared setup primitives.

## 2. Determinism hardening

- [x] 2.1 Replace dynamic/time-sensitive inputs with deterministic test values.
- [x] 2.2 Remove or rewrite order-dependent assertions in Kanban tests.

## 3. Validation

- [x] 3.1 Run Kanban-focused pytest selection and fix regressions.
- [x] 3.2 Run full `pytest` and ensure CI quality gates remain green.
