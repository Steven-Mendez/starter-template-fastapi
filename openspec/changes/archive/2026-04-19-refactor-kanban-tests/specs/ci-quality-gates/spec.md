## ADDED Requirements

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
