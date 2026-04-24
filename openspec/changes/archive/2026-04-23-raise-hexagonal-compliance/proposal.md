## Why

The template already applies hexagonal ideas, but key leaks still prevent it from being a high-confidence reference implementation: API adapters still depend on domain types, and repository interfaces/adapters still expose sub-entity persistence operations. We need stricter, measurable boundaries so the starter can consistently score at least 9/10 for hexagonal compliance.

## What Changes

- Tighten inbound adapter boundaries so HTTP routes and API mappers depend on application contracts, not domain models/results/errors.
- Define explicit application-layer read/write contracts (inputs, outputs, and error surface) to keep transport mapping at the adapter edge.
- Harden aggregate persistence boundaries by removing sub-entity orchestration APIs from driven repository ports and adapters.
- Extend architecture governance rules and tests to enforce zero-exception import boundaries for direct and transitive dependencies.
- Keep guardrails focused on enforceable boundaries (import order/layering and dependency-direction checks) without introducing synthetic architecture scoring tests.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `hexagonal-layer-boundaries`: Strengthen adapter purity rules so API depends on application contracts only and driven adapters remain pure I/O implementations.
- `application-mapping-boundary`: Require transport-to-application mapping both for inputs and outputs, including application-owned error/result contracts.
- `architecture-dependency-rules`: Add enforceable checks for API-to-domain leakage and stricter transitive dependency diagnostics.
- `architecture-import-governance`: Formalize governance purpose and require zero-exception enforcement of boundary policies.
- `repository-aggregate-compliance`: Enforce aggregate-root-only persistence contract with no child-entity CRUD-style orchestration APIs.

## Impact

- Affected code: `src/api/*`, `src/application/*`, `src/domain/kanban/repository/*`, `src/infrastructure/persistence/*`, and architecture tests under `tests/unit/*`.
- Affected docs/specs: OpenSpec capability specs listed above and architecture guidance in project docs.
- CI impact: architecture/compliance checks remain strict through lint/typecheck/tests and dependency-boundary enforcement.
