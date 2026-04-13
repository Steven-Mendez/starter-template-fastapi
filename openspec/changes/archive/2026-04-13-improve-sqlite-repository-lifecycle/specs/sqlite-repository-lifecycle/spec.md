## ADDED Requirements

### Requirement: SQLite repository SHALL support explicit close
The system SHALL provide an explicit close operation for SQLite repository instances, and the close operation SHALL be safe to call multiple times.

#### Scenario: Repository close called more than once
- **WHEN** `close()` is invoked multiple times on the same repository instance
- **THEN** the operation SHALL not raise an error

### Requirement: App lifecycle SHALL dispose repository resources
The system SHALL close repository resources on app shutdown when the configured repository implementation exposes a close operation.

#### Scenario: Test client exits app context
- **WHEN** application lifecycle shutdown occurs
- **THEN** repository cleanup SHALL be executed for close-capable repositories
