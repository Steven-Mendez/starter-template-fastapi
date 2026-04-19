# ci-quality-gates Specification

## Purpose

Ensure pull requests run the same lint, type-check, and test pipeline as local development so broken changes are caught before merge.
## Requirements
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

### Requirement: Kanban tests SHALL be deterministic across repeated runs

The system SHALL keep Kanban-focused tests deterministic so repeated executions in the same environment produce stable results.

#### Scenario: Re-running Kanban tests locally

- **WHEN** a developer runs the Kanban-focused pytest subset multiple times
- **THEN** the test results SHALL remain stable without order-dependent or time-dependent failures

### Requirement: Kanban test setup SHALL use reusable fixtures or builders

The system SHALL define reusable test setup primitives for board and card creation so tests remain concise and maintainable as scenarios grow.

#### Scenario: Adding a new Kanban test scenario

- **WHEN** a maintainer implements a new Kanban test
- **THEN** the test SHALL use shared fixtures/builders instead of duplicating full setup blocks
