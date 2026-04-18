## MODIFIED Requirements

### Requirement: Dependency rule SHALL be enforceable by tests
The system SHALL provide automated architecture tests that enforce inward-only dependency direction for modules under `src/`: infrastructure -> application -> domain.

#### Scenario: Forbidden import is detected
- **WHEN** a module in `src/domain/` or `src/application/` imports forbidden outer-layer modules
- **THEN** architecture tests SHALL fail with a clear boundary violation message

#### Scenario: Violation diagnostics include source and target modules
- **WHEN** a dependency violation occurs during architecture tests
- **THEN** test output SHALL include the source module path and forbidden import target

### Requirement: Architecture boundaries SHALL be explicit per layer
The system SHALL codify allowed and forbidden imports per layer to avoid ambiguous architectural drift, including domain, application, API adapters, and infrastructure modules.

#### Scenario: Allowed import matrix is validated in CI
- **WHEN** CI executes the unit suite
- **THEN** boundary checks SHALL validate imports for domain, application, API adapters, and infrastructure modules

#### Scenario: Boundary matrix is versioned with tests
- **WHEN** a new module is introduced in any architecture layer
- **THEN** boundary checks SHALL evaluate that module against the same allowed/forbidden import matrix rules
