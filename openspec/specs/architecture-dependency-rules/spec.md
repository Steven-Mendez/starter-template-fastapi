# architecture-dependency-rules Specification

## Purpose

Enforce clean/hexagonal dependency direction (inward-only: infrastructure toward application and domain) through explicit rules and automated tests so architectural boundaries do not drift.
## Requirements
### Requirement: Dependency rule SHALL be enforceable by tests
The system SHALL enforce inward dependency rules with checks that include static import analysis and runtime adapter dependency-graph analysis for API routes.

#### Scenario: Route dependency graph catches container-provider bypass
- **WHEN** API route dependency graphs are evaluated through FastAPI route metadata
- **THEN** tests SHALL fail if a route depends directly on container-provider callables intended for composition internals

#### Scenario: Concrete handler import bypass is rejected across import styles
- **WHEN** API dependency/provider modules are analyzed
- **THEN** tests SHALL fail on concrete command/query handler usage regardless of whether imports use `from ... import ...` or `import ... as ...` syntax

### Requirement: Architecture boundaries SHALL be explicit per layer
The system SHALL codify allowed and forbidden dependencies per layer, including import boundaries for API schema modules and dependency-provider modules.

#### Scenario: Allowed import matrix is validated in CI
- **WHEN** CI executes the unit suite
- **THEN** boundary checks SHALL validate imports for domain, application, API adapters, infrastructure modules, and root-level dependency modules used by `src/`

#### Scenario: API schema layer remains transport-owned
- **WHEN** modules under `src/api/schemas/*` are validated
- **THEN** those modules SHALL NOT import `src.application.contracts` directly

#### Scenario: Violation diagnostics are actionable
- **WHEN** boundary checks fail
- **THEN** output SHALL include violated rule, source module, and disallowed dependency target (or transitive path)
