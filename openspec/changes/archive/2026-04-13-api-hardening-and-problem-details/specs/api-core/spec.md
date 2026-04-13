## MODIFIED Requirements

### Requirement: Interactive API documentation
The system SHALL provide interactive OpenAPI-based documentation at `/docs` and alternative documentation at `/redoc` only when documentation exposure is enabled by runtime configuration.

#### Scenario: Documentation enabled in development mode
- **WHEN** the application runs with docs enabled
- **THEN** a client request to `/docs` SHALL succeed and present interactive API documentation

#### Scenario: Documentation disabled in production mode
- **WHEN** the application runs with docs disabled
- **THEN** a client request to `/docs` SHALL return `404`
