# kanban-application-use-cases Specification

## Purpose

Specify application-layer use cases for Kanban commands and queries and stable contracts for inbound adapters.

## Requirements

### Requirement: Kanban operations SHALL be exposed as application use cases

The system SHALL define application-layer use cases for Kanban commands and queries that orchestrate domain rules and outbound repository ports.

#### Scenario: Board create/list flows execute through use cases

- **WHEN** an inbound adapter handles board create or list requests
- **THEN** it SHALL invoke corresponding application use-case handlers for those operations

#### Scenario: Card move validation remains domain-driven

- **WHEN** a use case processes card moves between columns
- **THEN** it SHALL enforce domain move rules and return domain error outcomes for invalid moves

### Requirement: Use-case contracts SHALL be stable for adapters

The system SHALL expose typed application contracts that adapters can depend on without importing persistence implementation details.

#### Scenario: HTTP adapters bind to application interfaces

- **WHEN** API dependencies are wired
- **THEN** router handlers SHALL depend on use-case interfaces or handlers and SHALL NOT require concrete repository adapter imports
