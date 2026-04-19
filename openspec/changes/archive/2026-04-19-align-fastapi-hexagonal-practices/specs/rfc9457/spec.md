## MODIFIED Requirements

### Requirement: Problem Details media type for errors
The system SHALL use the `application/problem+json` media type for error responses produced by exception handlers for HTTP errors, request validation failures, and unexpected server exceptions.

#### Scenario: Client receives a not-found error
- **WHEN** a request results in a `404` response handled as a Problem Detail
- **THEN** the response `Content-Type` SHALL indicate `application/problem+json`
- **THEN** the JSON body SHALL include `type`, `title`, and `status`, and SHOULD include `detail` and `instance` when applicable

#### Scenario: Unhandled exception returns sanitized payload
- **WHEN** a request fails with an unhandled exception
- **THEN** the response SHALL be a `500` Problem Details payload with non-sensitive generic detail text
- **THEN** the payload MAY include safe correlation extensions (for example `request_id`) and SHALL NOT expose traceback internals
