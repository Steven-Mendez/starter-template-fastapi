## MODIFIED Requirements

### Requirement: Dependency rule SHALL be enforceable by tests
The system SHALL provide automated architecture tests that enforce inward-only dependency direction (infrastructure -> application -> domain) for direct imports and transitive import paths, including API-to-domain leakage checks.

#### Scenario: Forbidden direct import is detected
- **WHEN** a module in domain or application imports forbidden outer-layer modules
- **THEN** architecture tests SHALL fail with a clear boundary violation message

#### Scenario: Forbidden transitive dependency path is detected
- **WHEN** an API module reaches infrastructure through one or more intermediate modules
- **THEN** architecture tests SHALL fail and report the transitive module path causing the violation

#### Scenario: API-to-domain contract leakage is detected
- **WHEN** an API adapter module imports domain models, domain shared errors, or domain result modules
- **THEN** architecture tests SHALL fail and identify the offending import edge

### Requirement: Architecture boundaries SHALL be explicit per layer
The system SHALL codify allowed and forbidden imports per layer to avoid ambiguous architectural drift, and SHALL apply this policy to modules under `src/` and root-level modules imported by `src/` modules.

#### Scenario: Allowed import matrix is validated in CI
- **WHEN** CI executes the unit suite
- **THEN** boundary checks SHALL validate imports for domain, application, API adapters, infrastructure modules, and root-level dependency modules used by `src/`

#### Scenario: API layer disallows direct domain dependencies
- **WHEN** API modules are validated against the architecture matrix
- **THEN** the allowed dependency set SHALL include application contracts but SHALL exclude direct imports from domain contract modules

#### Scenario: Violation diagnostics are actionable
- **WHEN** boundary checks fail
- **THEN** output SHALL include violated rule, source module, and disallowed dependency target (or transitive path)
