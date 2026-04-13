## MODIFIED Requirements

### Requirement: Problem Details media type for errors
The system SHALL use the `application/problem+json` media type for error responses produced by the application’s exception handlers for `HTTPException`, request body/query validation failures, and unexpected server exceptions.

#### Scenario: Client receives a not-found error
- **WHEN** a request results in a `404` response handled as a Problem Detail
- **THEN** the response `Content-Type` SHALL indicate `application/problem+json`
- **THEN** the JSON body SHALL include `type`, `title`, and `status`, and SHOULD include `detail` and `instance` when applicable

#### Scenario: Client triggers unexpected server exception
- **WHEN** a request fails with an unhandled exception
- **THEN** the response SHALL be emitted as Problem Details with status `500`
- **THEN** the payload SHALL include stable top-level RFC 9457 fields and MAY include correlation extensions

### Requirement: Validation errors remain structured
The system SHALL represent request validation failures as Problem Details with HTTP status `422`, and SHALL include a machine-readable list of validation errors in an extension member so clients can locate invalid fields.

#### Scenario: Client sends invalid payload
- **WHEN** a request fails Pydantic validation
- **THEN** the response status code SHALL be `422`
- **THEN** the Problem Details body SHALL include an `errors` array (or equivalent extension) carrying validation diagnostics
