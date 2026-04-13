# api-core Specification

## Purpose
TBD - created by archiving change init-fastapi-project. Update Purpose after archive.
## Requirements
### Requirement: Root endpoint identifies the service

The system SHALL expose `GET /` and return a JSON object that includes the application name and a short human-readable message.

#### Scenario: Client requests service info

- **WHEN** a client sends `GET /` with an `Accept` header compatible with JSON
- **THEN** the response status code SHALL be `200`
- **THEN** the response body SHALL be JSON and SHALL include a field identifying the service (for example `name` or `message`)

### Requirement: Health endpoint for liveness

The system SHALL expose `GET /health` for liveness checks and return JSON indicating the service is running.

#### Scenario: Load balancer probes health

- **WHEN** a client sends `GET /health`
- **THEN** the response status code SHALL be `200`
- **THEN** the response body SHALL be JSON and SHALL include a field indicating healthy status (for example `status` with value `ok`)

### Requirement: Interactive API documentation

When the application is served with default FastAPI settings, the system SHALL provide interactive OpenAPI-based documentation at `/docs` and alternative documentation at `/redoc` without additional configuration for this change.

#### Scenario: Developer opens Swagger UI

- **WHEN** a client sends `GET /docs`
- **THEN** the response SHALL succeed (status in the 2xx range) and present the interactive API documentation UI

