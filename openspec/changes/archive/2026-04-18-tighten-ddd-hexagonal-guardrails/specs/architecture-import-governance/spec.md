## ADDED Requirements

### Requirement: Layer import governance SHALL be enforced from source imports
The system SHALL enforce layer dependency direction using source-level import analysis for modules under `src/`, rather than relying only on text-fragment assertions.

#### Scenario: Domain imports forbidden outer layer module
- **WHEN** a module inside `src/domain/` imports from `src/application/`, `src/api/`, or `src/infrastructure/`
- **THEN** architecture tests SHALL fail and include the violating module path and forbidden import target

#### Scenario: Application imports forbidden adapter layer module
- **WHEN** a module inside `src/application/` imports from `src/api/` or `src/infrastructure/`
- **THEN** architecture tests SHALL fail and include a dependency-rule violation message

### Requirement: Governance output SHALL provide actionable diagnostics
The system SHALL emit diagnostics that identify violated rules so maintainers can fix boundary drift quickly.

#### Scenario: Boundary check failure in CI
- **WHEN** CI executes architecture tests and a rule violation exists
- **THEN** the failure output SHALL identify the violated rule, source module, and disallowed dependency target
