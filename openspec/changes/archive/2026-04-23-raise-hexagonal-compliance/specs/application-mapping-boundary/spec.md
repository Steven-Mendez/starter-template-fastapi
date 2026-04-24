## MODIFIED Requirements

### Requirement: API adapters SHALL map transport DTOs at the boundary
The system SHALL perform request, response, and error/result mapping at the HTTP adapter boundary so application handlers operate on internal application contracts instead of transport DTOs or domain internals.

#### Scenario: Request mapping happens before use-case invocation
- **WHEN** an API endpoint receives a request payload
- **THEN** the adapter SHALL map the payload to an application input contract before invoking a use case

#### Scenario: Response mapping happens after handler invocation
- **WHEN** an application handler returns a successful result
- **THEN** the API adapter SHALL map that result to transport response schemas before writing the HTTP response

#### Scenario: Error/result mapping remains adapter-owned
- **WHEN** an application handler returns a failure contract
- **THEN** the API adapter SHALL map that failure to transport error responses without importing domain error/result modules

### Requirement: Application contracts SHALL remain transport-agnostic
The system SHALL keep application-layer contracts free of FastAPI/Pydantic transport concerns and SHALL expose adapter-facing contracts from application modules rather than from domain result wrappers.

#### Scenario: Application module dependency check
- **WHEN** application modules are inspected
- **THEN** they SHALL NOT depend directly on HTTP request/response schema modules

#### Scenario: Handler contracts remain independent of FastAPI dependency objects
- **WHEN** command/query handler contracts are imported by adapters
- **THEN** application contracts SHALL expose plain Python types and SHALL NOT require FastAPI `Depends` or request objects

#### Scenario: Adapter uses application-level result contracts
- **WHEN** API adapters import result and error contracts for mapping
- **THEN** those imports SHALL come from application-layer contracts and SHALL NOT come from domain shared result modules
