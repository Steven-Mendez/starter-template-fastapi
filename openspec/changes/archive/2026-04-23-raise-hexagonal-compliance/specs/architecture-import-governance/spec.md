## MODIFIED Requirements

### Requirement: Import governance SHALL enforce direct and transitive boundaries
The system SHALL enforce architecture boundaries using source import analysis over governed modules and SHALL fail when a forbidden dependency is present directly or through transitive import paths, including API-to-domain contract leakage.

#### Scenario: Forbidden transitive path is detected
- **WHEN** an API-layer module reaches an infrastructure module through one or more intermediate modules
- **THEN** architecture checks SHALL fail and report the full path from source to forbidden target

#### Scenario: Forbidden API-to-domain contract edge is detected
- **WHEN** an API-layer module imports domain contract modules directly
- **THEN** import governance SHALL fail and report the violating source and target modules

### Requirement: Governance mode SHALL be zero-exception in CI
The system SHALL run architecture boundary checks in zero-exception mode in CI, without temporary allowlist bypasses for forbidden dependencies.

#### Scenario: Violation exists in pull request
- **WHEN** CI runs architecture tests for a branch containing a forbidden dependency edge
- **THEN** the pipeline SHALL fail until the violating dependency is removed

#### Scenario: Boundary policy has no bypass switches
- **WHEN** CI configuration is evaluated for architecture checks
- **THEN** the governance check SHALL run without exception allowlists or environment-based skip flags
