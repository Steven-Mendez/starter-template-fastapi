# architecture-dependency-rules Specification

## Purpose

Enforce clean/hexagonal dependency direction (inward-only: infrastructure toward application and domain) through explicit rules and automated tests so architectural boundaries do not drift.

## Requirements

### Requirement: Dependency rule SHALL be enforceable by tests

The system SHALL provide automated architecture tests that enforce inward-only dependency direction: infrastructure -> application -> domain.

#### Scenario: Forbidden import is detected

- **WHEN** a module in domain or application imports forbidden outer-layer modules
- **THEN** architecture tests SHALL fail with a clear boundary violation message

### Requirement: Architecture boundaries SHALL be explicit per layer

The system SHALL codify allowed and forbidden imports per layer to avoid ambiguous architectural drift.

#### Scenario: Allowed import matrix is validated in CI

- **WHEN** CI executes the unit suite
- **THEN** boundary checks SHALL validate imports for domain, application, API adapters, and infrastructure modules
