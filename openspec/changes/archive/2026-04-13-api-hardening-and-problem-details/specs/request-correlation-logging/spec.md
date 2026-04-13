## ADDED Requirements

### Requirement: API SHALL include a request identifier per request
The system SHALL attach a request identifier to each request context and responses, generating one when absent.

#### Scenario: Request without incoming request ID
- **WHEN** a client sends a request without `X-Request-ID`
- **THEN** the server SHALL generate a request identifier
- **THEN** the response SHALL include `X-Request-ID` with that generated value

### Requirement: Error responses SHALL expose correlation identifier
The system SHALL include the request identifier in Problem Details extension members for traceability.

#### Scenario: Handler raises an exception
- **WHEN** a request fails and returns Problem Details
- **THEN** the response body SHALL include an extension field containing the request identifier
