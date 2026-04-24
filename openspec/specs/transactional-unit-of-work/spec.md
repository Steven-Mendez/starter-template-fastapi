# transactional-unit-of-work Specification

## Purpose

Define an application-layer transactional boundary that coordinates repository writes atomically and keeps commit/rollback responsibilities explicit.

## Requirements

### Requirement: Transactional Unit of Work abstraction

The system SHALL define a `UnitOfWork` protocol to manage atomic transactions in the application layer.

#### Scenario: Unit of work ensures atomicity

- **WHEN** a command handler wraps repository actions within a `UnitOfWork` context
- **THEN** it SHALL commit on success and rollback on failure transparently
