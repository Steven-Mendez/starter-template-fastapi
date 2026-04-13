## Why

Business rules are currently embedded directly in repository methods, which makes rule reuse and rule-level testing harder. We want explicit, composable domain specifications so rule intent is clearer and easier to validate independently.

## What Changes

- Introduce a reusable Specification Pattern foundation for domain rules.
- Add Kanban-specific specifications for card movement invariants.
- Refactor repository implementations to evaluate movement rules through specifications.
- Add focused unit tests for specification composition and behavior (TDD-first).

## Capabilities

### New Capabilities
- `domain-specification-pattern`: Reusable specification primitives and composition for domain rule evaluation.

### Modified Capabilities
- `kanban-repository`: Card move validation SHALL be expressed through specification objects instead of ad hoc inline checks.

## Impact

- Affected code: `kanban/` domain and repository modules, plus unit tests.
- No API contract change expected; behavior should remain equivalent for clients.
- Improves maintainability and future extension of domain rules.
