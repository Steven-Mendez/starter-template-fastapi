# repository-aggregate-compliance Specification

## Purpose

Enforce the aggregate root repository pattern for the Kanban bounded context, ensuring sub-entities are managed through their aggregate root.

## Requirements

### Requirement: Repositories SHALL manage Data implicitly through the Aggregate Root

The system SHALL enforce the pattern of "One repository per AGGREGATE", treating the Kanban `Board` as the Aggregate Root for fetching and interacting with underlying entities (Cards, Columns).

#### Scenario: Sub-entities are not persisted individually

- **WHEN** updating a card's position or creating a new column
- **THEN** the database adapter interface SHALL be configured to receive pre-calculated, verified state values dictating the persistence outcome rather than orchestrating updates on individual child entities on its own.
