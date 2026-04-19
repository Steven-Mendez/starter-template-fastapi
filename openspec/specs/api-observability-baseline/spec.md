# api-observability-baseline Specification

## Purpose

Define baseline API observability: structured request lifecycle logging and health responses that reflect persistence readiness.
## Requirements
### Requirement: API SHALL emit structured request logs
The system SHALL emit structured log entries for request lifecycle events with stable fields including request ID, method, path, status code, and duration.

#### Scenario: Request completes successfully
- **WHEN** a client request returns a successful response
- **THEN** the application SHALL emit a structured log entry containing request metadata and status

#### Scenario: Request fails with unhandled exception
- **WHEN** a request raises an unhandled exception handled by global exception handling
- **THEN** the application SHALL emit a structured error log entry containing request ID, method, path, and error class before responding

### Requirement: Health endpoint SHALL report persistence readiness

The system SHALL report persistence backend readiness in health responses suitable for operational checks.

#### Scenario: Persistence backend unavailable

- **WHEN** the configured persistence backend is not ready
- **THEN** the health response SHALL indicate unhealthy readiness status for persistence
