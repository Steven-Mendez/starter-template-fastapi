## ADDED Requirements

### Requirement: Pull requests SHALL run quality gates in CI
The system SHALL execute linting, static type checks, and automated tests for each pull request targeting the default branch.

#### Scenario: Pull request triggers CI
- **WHEN** a contributor opens or updates a pull request
- **THEN** CI SHALL run the quality workflow automatically
- **THEN** the workflow SHALL include lint, typecheck, and pytest stages

### Requirement: CI status SHALL block merge on failures
The system SHALL report failing quality checks as a failed status so maintainers can prevent merging broken changes.

#### Scenario: Lint stage fails
- **WHEN** linting returns a non-zero exit code
- **THEN** the workflow SHALL fail
- **THEN** merge readiness SHALL be blocked until the failure is fixed
