## Context

The architecture uses a unit-of-work abstraction, but at least one repository path can commit directly, creating overlapping responsibility. This weakens atomic guarantees and makes command behavior dependent on adapter choice. To align with hexagonal principles, transaction lifecycle must be controlled by the application boundary through a single contract.

## Goals / Non-Goals

**Goals:**
- Make unit-of-work the sole transaction owner for command-side mutations.
- Define explicit repository rules for no-commit behavior inside command execution.
- Guarantee rollback semantics on failure and no partial writes for a single command.
- Make transactional behavior testable through reusable contract tests.

**Non-Goals:**
- Introducing distributed transactions or saga orchestration.
- Changing query-side consistency model.
- Replacing the persistence technology stack.

## Decisions

1. Adopt unit-of-work-only commit model for command flows.
   - Rationale: a single owner prevents duplicate commits and clarifies failure behavior.
   - Alternative: allow repository-level commit flags. Rejected due to configurational complexity and accidental misuse.

2. Split repository implementations by intent if needed (session-scoped command repository vs standalone utility repository).
   - Rationale: explicit types encode behavioral guarantees and reduce implicit state.
   - Alternative: one repository with dynamic branching. Rejected due to hidden behavior.

3. Require command handlers to own lifecycle (`begin`, `commit`, `rollback`) via UoW abstraction.
   - Rationale: application layer controls atomic business operations independent of adapter implementation.

4. Add conformance tests for commit-once, rollback-on-exception, and no-write-after-failure scenarios.
   - Rationale: prevents regressions when adapters evolve.

## Risks / Trade-offs

- [Risk] Refactor may break implicit assumptions in existing command paths → Mitigation: stage migration and run end-to-end mutation scenarios before release.
- [Risk] More explicit lifecycle code in handlers can increase verbosity → Mitigation: provide helper abstraction or context manager in application layer.
- [Risk] Existing adapters may need parallel implementations during transition → Mitigation: use deprecation window and clear adapter compliance checklist.
