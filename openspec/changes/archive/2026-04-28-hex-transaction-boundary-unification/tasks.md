## 1. Transaction ownership hardening

- [x] 1.1 Define and document unit-of-work as exclusive transaction owner for command flows.
- [x] 1.2 Refactor command repositories to remove implicit commit/rollback behavior.
- [x] 1.3 Ensure command handlers consistently manage unit-of-work lifecycle.

## 2. Adapter alignment and migration safety

- [x] 2.1 Introduce explicit repository variants or interfaces if behavioral separation is required.
- [x] 2.2 Add compatibility guardrails and deprecation notices for legacy self-commit paths.
- [x] 2.3 Validate mutation paths for atomicity under failure injections.

## 3. Verification

- [x] 3.1 Implement contract tests for commit-once and rollback-on-failure.
- [x] 3.2 Add integration tests to confirm no partial writes across multi-step commands.
- [x] 3.3 Add regression tests covering concurrency and infrastructure exceptions within UoW flows.
