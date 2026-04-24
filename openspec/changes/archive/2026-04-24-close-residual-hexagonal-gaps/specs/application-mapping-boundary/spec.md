## MODIFIED Requirements

### Requirement: API adapters SHALL map transport DTOs at the boundary
The system SHALL perform request, response, and error/result mapping at the HTTP adapter boundary so application handlers operate on internal application contracts instead of transport DTOs or domain internals, including translation of wire-specific enums/value literals.

#### Scenario: Request mapping happens before use-case invocation
- **WHEN** an API endpoint receives a request payload
- **THEN** the adapter SHALL map the payload to an application input contract before invoking a use case

#### Scenario: Wire enum/value translation is adapter-owned
- **WHEN** transport payloads contain wire-specific enum/value types
- **THEN** API mappers SHALL translate those values to application contract types before calling handlers

#### Scenario: Response mapping happens after handler invocation
- **WHEN** an application handler returns a successful result
- **THEN** the API adapter SHALL map that result to transport response schemas before writing the HTTP response

#### Scenario: Error/result mapping remains adapter-owned
- **WHEN** an application handler returns a failure contract
- **THEN** the API adapter SHALL map that failure to transport error responses without importing domain error/result modules

## ADDED Requirements

### Requirement: API schema modules SHALL remain transport-owned
The system SHALL define HTTP request/response schema types in API schema modules and SHALL NOT import application contract modules directly from `src/api/schemas/*`.

#### Scenario: Schema module dependency boundary
- **WHEN** modules under `src/api/schemas/*` are analyzed
- **THEN** they SHALL depend on transport validation primitives and local schema types, and SHALL NOT import `src.application.contracts`

#### Scenario: Application contract coupling stays inside mappers
- **WHEN** transport values must be converted to application types
- **THEN** conversion logic SHALL exist in adapter mapping modules (for example `src/api/mappers/*`) rather than schema definitions
