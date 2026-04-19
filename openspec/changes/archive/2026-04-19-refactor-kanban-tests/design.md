## Context

Kanban tests validate core behavior, but some scenarios duplicate setup and encode data inline, making updates noisy. The refactor should improve structure and test ergonomics without changing domain or API behavior.

## Goals / Non-Goals

**Goals:**

- Reduce duplication in Kanban tests through shared fixtures and builders.
- Improve determinism by controlling IDs, timestamps, and random inputs in tests.
- Keep assertions behavior-focused and stable across repeated runs.

**Non-Goals:**

- No changes to production business logic or endpoint contracts.
- No replacement of the project test framework.
- No expansion of scope to unrelated test suites.

## Decisions

- Use `conftest.py` fixtures and small builder helpers for reusable board/card setup.
- Prefer explicit deterministic inputs in tests (fixed timestamps, seeded/random-free values).
- Keep existing behavior assertions, but simplify test arrangement and naming for readability.

## Risks / Trade-offs

- **[Risk] Shared fixtures can hide intent** -> **Mitigation**: keep fixtures small and compose them in each test for clarity.
- **[Risk] Refactor may accidentally drop coverage** -> **Mitigation**: map old scenarios to new tests and verify with targeted pytest runs.
- **[Risk] Large file moves can complicate review** -> **Mitigation**: refactor in small, grouped commits by module.

## Migration Plan

1. Introduce reusable fixtures/builders for Kanban entities.
2. Refactor existing Kanban tests module-by-module to use shared setup.
3. Run Kanban-focused tests, then full `pytest` to confirm parity.
4. Keep rollback simple by reverting specific test-module refactor commits.

## Open Questions

- Should fixtures live only at the Kanban test package level or be promoted to shared test utilities for other domains?
