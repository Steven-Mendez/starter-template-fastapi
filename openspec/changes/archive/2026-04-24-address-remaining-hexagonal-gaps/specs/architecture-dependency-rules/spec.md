## MODIFIED Requirements

### Requirement: Dependency rule SHALL be enforceable by tests
The system SHALL enforce inward dependency rules with checks that include static import analysis and runtime adapter dependency-graph analysis for API routes.

#### Scenario: Route dependency graph catches container-provider bypass
- **WHEN** API route dependency graphs are evaluated through FastAPI route metadata
- **THEN** tests SHALL fail if a route depends directly on container-provider callables intended for composition internals

#### Scenario: Concrete handler import bypass is rejected across import styles
- **WHEN** API dependency/provider modules are analyzed
- **THEN** tests SHALL fail on concrete command/query handler usage regardless of whether imports use `from ... import ...` or `import ... as ...` syntax
