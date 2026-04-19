# lightweight-cqrs Specification

## Purpose

Define in-process command/query separation for application handlers so read and write concerns remain isolated without introducing distributed CQRS infrastructure.
## Requirements
### Requirement: Application layer SHALL separate command and query responsibilities
The system SHALL define dedicated command handlers and query handlers so write operations and read operations are not mixed in the same application contract.

#### Scenario: Board creation uses command handler
- **WHEN** an API adapter processes a board creation request
- **THEN** it SHALL invoke a command-oriented application handler

#### Scenario: Board detail retrieval uses query handler
- **WHEN** an API adapter processes a board retrieval request
- **THEN** it SHALL invoke a query-oriented application handler

#### Scenario: Read endpoint does not depend on command handler
- **WHEN** dependency annotations for `GET` routes are inspected
- **THEN** those routes SHALL depend on query handlers and SHALL NOT depend on command handlers

### Requirement: Lightweight CQRS SHALL avoid advanced infrastructure complexity
The system SHALL implement CQRS separation only at code-structure level and SHALL NOT require distributed command buses, event sourcing, or asynchronous projection pipelines.

#### Scenario: CQRS implementation remains in-process
- **WHEN** command and query handlers are wired
- **THEN** they SHALL execute in-process using the existing application composition root

### Requirement: Command handlers SHALL demarcate transaction boundaries explicitly

The system SHALL require that all persistence mutations executed by command handlers are safeguarded inside a clear Transactional Boundary (Unit of Work).

#### Scenario: Mutations occur within Unit of Work

- **WHEN** a command handler completes its state modification workflow
- **THEN** it SHALL interact with a standard `UnitOfWork` to orchestrate commits robustly against partial failures
