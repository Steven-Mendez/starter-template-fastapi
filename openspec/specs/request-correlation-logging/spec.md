# request-correlation-logging Specification

## Purpose

Attach and emit request identifiers for traceable request/response flows and correlation with error payloads.
## Requirements
### Requirement: API SHALL include a request identifier per request
The system SHALL attach a request identifier to each request context and response, generating one when absent and preserving the incoming value when present.

#### Scenario: Request carries caller-provided ID
- **WHEN** a client sends a request with `X-Request-ID`
- **THEN** the response SHALL include the same `X-Request-ID` value

### Requirement: Error responses SHALL expose correlation identifier
The system SHALL include request correlation identifiers in Problem Details payloads and structured error telemetry for unhandled exceptions.

#### Scenario: Unhandled exception is emitted
- **WHEN** a request fails with an unhandled exception
- **THEN** the structured error log entry SHALL include request ID, method, path, status code, and error class
