## ADDED Requirements

### Requirement: Problem Details responses carry a stable `type` URN

Every Problem Details response with a recognized domain error class SHALL set `type` to a stable URN of the form `urn:problem:<domain>:<code>`. The URN catalog is defined as `ProblemType(StrEnum)` in `src/app_platform/api/problem_types.py` and documented in `docs/api.md`. `type: "about:blank"` is reserved for genuinely uncategorized errors and SHALL be emitted via `ProblemType.ABOUT_BLANK`.

#### Scenario: Invalid credentials response carries the auth URN

- **GIVEN** a registered user
- **WHEN** a client submits the wrong password to `POST /auth/login`
- **THEN** the response body's `type` equals `urn:problem:auth:invalid-credentials`
- **AND** the body's `status` equals `401`

#### Scenario: Permission-denied carries the authz URN

- **GIVEN** an authenticated non-admin principal
- **WHEN** the client calls `GET /admin/users`
- **THEN** the response body's `type` equals `urn:problem:authz:permission-denied`
- **AND** the body's `status` equals `403`

#### Scenario: Validation failure carries the validation URN

- **GIVEN** a malformed request body
- **WHEN** the client submits it to any validating endpoint
- **THEN** the response body's `type` equals `urn:problem:validation:failed`
- **AND** the body's `status` equals `422`

#### Scenario: Uncategorized error falls back to about:blank

- **GIVEN** an exception class with no `ProblemType` mapping
- **WHEN** the generic handler renders it
- **THEN** the response body's `type` equals `about:blank`
