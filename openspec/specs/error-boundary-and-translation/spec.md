# error-boundary-and-translation Specification

## Purpose
TBD - created by archiving change hex-error-boundaries. Update Purpose after archive.
## Requirements
### Requirement: Application Error Taxonomy
The system MUST define a canonical application error taxonomy that distinguishes domain rule violations, concurrency conflicts, persistence availability failures, validation failures, and unexpected internal failures.

#### Scenario: Concurrency conflict represented as typed application error
- **WHEN** an outbound persistence adapter detects optimistic lock mismatch during an update
- **THEN** the application boundary returns an application error typed as concurrency conflict with a stable machine-readable code

#### Scenario: Infrastructure outage represented without transport leakage
- **WHEN** an outbound adapter encounters a storage availability error
- **THEN** the application boundary returns an application error typed as persistence unavailable without exposing ORM- or driver-specific types

### Requirement: Adapter-to-Application Error Translation Boundary
The system MUST enforce a single translation boundary where infrastructure exceptions are mapped to application errors before crossing into inbound transport adapters.

#### Scenario: Inbound adapter receives only application error
- **WHEN** a use case fails due to a translated persistence conflict
- **THEN** the HTTP adapter receives only the application error contract and MUST NOT inspect adapter exception classes

#### Scenario: Unknown infrastructure exception normalization
- **WHEN** an unclassified infrastructure exception occurs
- **THEN** the boundary maps it to a generic internal application failure code and records diagnostic metadata in logs

### Requirement: Deterministic HTTP Error Contract
The system MUST map each application error category to a deterministic HTTP status and response payload schema.

#### Scenario: Conflict maps to HTTP 409
- **WHEN** the application returns concurrency conflict
- **THEN** the HTTP response status is 409 and payload includes `code`, `message`, and optional `details`

#### Scenario: Persistence unavailable maps to HTTP 503
- **WHEN** the application returns persistence unavailable
- **THEN** the HTTP response status is 503 and payload includes `code`, `message`, and retry-safe wording

### Requirement: Observability for Translated Failures
The system MUST emit structured logs with stable error code, category, correlation identifier, and root-cause class name for every translated technical failure.

#### Scenario: Structured error log emitted on translation
- **WHEN** a technical failure is translated to an application error
- **THEN** one structured error event is emitted including `error_code`, `category`, `trace_id`, and `source_exception`
