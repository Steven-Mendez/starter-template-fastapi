# application-mapping-boundary Specification

## Purpose

Keep HTTP transport data transfer objects mapped at the API adapter edge while application use cases and ports operate on internal contracts.

## Requirements

### Requirement: API adapters SHALL map transport DTOs at the boundary

The system SHALL perform request/response mapping at the HTTP adapter boundary so application ports and use cases operate on internal contracts instead of transport DTOs.

#### Scenario: Request mapping happens before use-case invocation

- **WHEN** an API endpoint receives a request payload
- **THEN** the adapter SHALL map the payload to an application input contract before invoking a use case

### Requirement: Application contracts SHALL remain transport-agnostic

The system SHALL keep application-layer contracts free of FastAPI/Pydantic request-response concerns.

#### Scenario: Application module dependency check

- **WHEN** application modules are inspected
- **THEN** they SHALL NOT depend directly on HTTP request/response schema modules
