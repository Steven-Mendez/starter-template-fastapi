## MODIFIED Requirements

### Requirement: Kanban repository SHALL support durable SQLite storage

The system SHALL provide a PostgreSQL-backed repository implementation, via SQLModel, that persists boards, columns, and cards across application restarts.

#### Scenario: Data persists after restart

- **WHEN** a board is created using PostgreSQL storage and the app restarts
- **THEN** querying boards SHALL include the previously created board

### Requirement: SQLite repository SHALL preserve domain error semantics

The system SHALL return the same domain-level success and error result patterns as the in-memory repository for equivalent operations.

#### Scenario: Invalid card move in relational repository

- **WHEN** a card is moved to a column in a different board
- **THEN** the repository SHALL return the invalid move error result code
