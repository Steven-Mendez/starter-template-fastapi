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
The system MUST enforce a single translation boundary where infrastructure exceptions are mapped to application errors before crossing into inbound transport adapters, AND a single translation boundary where domain exceptions are mapped to application errors before crossing into inbound transport adapters. Inbound adapters consume only `ApplicationError` values.

#### Scenario: Inbound adapter receives only application error
- **WHEN** a use case fails due to a translated persistence conflict
- **THEN** the HTTP adapter receives only the application error contract and MUST NOT inspect adapter exception classes

#### Scenario: Unknown infrastructure exception normalization
- **WHEN** an unclassified infrastructure exception occurs
- **THEN** the boundary maps it to a generic internal application failure code and records diagnostic metadata in logs

#### Scenario: Inbound adapter receives translated domain exception
- **WHEN** a use case raises a `KanbanDomainError` and translates it inside the use case
- **THEN** the HTTP adapter receives only the resulting `ApplicationError` value and MUST NOT import or reference `KanbanDomainError` or any subclass

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

### Requirement: Domain Rule Violations Use Typed Domain Exceptions
The domain layer MUST signal business invariant violations and aggregate-internal precondition failures by raising typed exceptions that descend from a single `KanbanDomainError` base class. Returning enum sentinels (for example `KanbanError | None`) or `Result[T, KanbanError]` from domain methods to encode invariant violations is forbidden.

#### Scenario: Aggregate method raises typed exception on invariant violation
- **WHEN** `Board.delete_column` is called with a `column_id` that does not exist on the board
- **THEN** the method raises `ColumnNotFoundError` (a subclass of `KanbanDomainError`) and does not return an error sentinel

#### Scenario: Aggregate method raises typed exception on invalid card move
- **WHEN** `Board.move_card` is called with a target column that does not exist or that violates a domain rule
- **THEN** the method raises `InvalidCardMoveError` (a subclass of `KanbanDomainError`) and does not return an error sentinel

#### Scenario: Sentinel return on domain method rejected
- **WHEN** any public method on a class under `src/domain/kanban/models/` declares a return type whose union includes a member of `src.domain.shared.errors.KanbanError` or `src.application.shared.errors.ApplicationError`
- **THEN** the architecture conformance suite fails

### Requirement: Single Domain-to-Application Translation Boundary
Application use cases MUST translate raised domain exceptions into `ApplicationError` values at exactly one place per use case (a `try/except KanbanDomainError` block or an equivalent translator helper). Inbound adapters MUST NOT inspect domain exception classes.

#### Scenario: Use case translates domain exception once
- **WHEN** a domain method raises `ColumnNotFoundError` during command execution
- **THEN** the surrounding use case catches it and returns `AppErr(ApplicationError.COLUMN_NOT_FOUND)` exactly once before returning to the caller

#### Scenario: Inbound adapter inspects domain exception is rejected
- **WHEN** any module under `src/api/` references `KanbanDomainError` or any of its subclasses
- **THEN** the architecture conformance suite fails

### Requirement: Domain Exception Hierarchy is Closed and Mapped
The set of `KanbanDomainError` subclasses MUST be closed (defined in a single domain module) and exhaustively mapped to `ApplicationError` values via the existing `from_domain_error` boundary. Adding a new domain exception subclass without adding the corresponding mapping entry MUST fail the build.

#### Scenario: Closed hierarchy enforced
- **WHEN** the conformance suite enumerates subclasses of `KanbanDomainError`
- **THEN** every subclass is defined inside `src/domain/kanban/exceptions.py` (or an explicitly-listed peer module) and there is exactly one `ApplicationError` mapping entry for it

#### Scenario: Unmapped domain exception fails build
- **WHEN** a new `KanbanDomainError` subclass is added without a corresponding entry in the application-side translator table
- **THEN** the conformance suite fails with a diagnostic naming the missing exception and the translator location
