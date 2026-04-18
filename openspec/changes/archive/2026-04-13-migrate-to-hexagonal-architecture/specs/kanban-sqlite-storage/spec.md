## MODIFIED Requirements

### Requirement: Kanban repository SHALL support durable SQLite storage

The system SHALL provide a SQLite-backed repository implementation, via SQLModel, that persists boards, columns, and cards across application restarts.

#### Scenario: Data persists after restart

- **WHEN** a board is created using SQLite storage and the app restarts
- **THEN** querying boards SHALL include the previously created board
