## Why

The current migration already follows clean DDD/hexagonal structure, but enforcement is still light and can drift as the codebase grows. We need stronger, testable guardrails plus explicit persistence/session boundaries to keep architecture intent durable.

## What Changes

- Strengthen architecture boundary checks from string-based smoke tests to import-graph style assertions that fail on real dependency violations.
- Clarify and enforce command/query usage in API adapters so routers remain thin orchestration layers.
- Tighten persistence adapter rules for SQLModel usage, including explicit session lifecycle and transaction boundaries aligned with current FastAPI dependency/lifespan practices.
- Add architecture-focused tests and documentation updates that make dependency direction and adapter responsibilities auditable in CI.

## Capabilities

### New Capabilities
- `architecture-import-governance`: Enforce allowed/forbidden cross-layer imports with explicit test coverage and failure diagnostics.
- `persistence-session-boundary`: Define and validate repository session/transaction lifecycle contracts across in-memory and SQLModel adapters.

### Modified Capabilities
- `architecture-dependency-rules`: Expand requirements from minimal checks to comprehensive, automated boundary enforcement.
- `hexagonal-layer-boundaries`: Tighten requirements for API -> application handler delegation and prohibition of direct repository access from adapters.
- `lightweight-cqrs`: Strengthen separation requirements so command/query handlers remain distinct and observable in tests.
- `sqlmodel-postgresql-persistence`: Refine requirements for adapter-only SQLModel concerns (engine/session handling, no domain leakage).

## Impact

- Affected code: `tests/unit/` architecture tests, `src/api/`, `src/application/`, `src/infrastructure/persistence/`, and dependency wiring in `dependencies.py` / composition root.
- Affected quality gates: `pytest` unit suite and CI boundary checks.
- External dependencies: no required runtime dependency changes expected; tooling may add one lightweight import analysis dependency if needed.
