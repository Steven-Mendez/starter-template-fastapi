## ADDED Requirements

### Requirement: 422 responses always include a `violations` array

The 422 Problem Details response SHALL always include a `violations: list[Violation]` field with one entry per failed field. A `Violation` is an object with:

- `loc: list[str | int]` — the canonical Pydantic location path (e.g. `["body", "address", "zip"]`), preserving order and types.
- `type: str` — the Pydantic error type (e.g. `value_error`, `missing`, `string_too_short`).
- `msg: str` — the human-readable message.
- `input: object | null` — the offending input value. SHALL be present in non-production environments. SHALL be omitted (key absent) when `APP_ENVIRONMENT=production`.

The `loc`, `type`, and `msg` fields SHALL be identical in development and production.

#### Scenario: Two-field validation failure in development

- **GIVEN** `APP_ENVIRONMENT=development`
- **WHEN** the client submits a request body with an invalid email AND a missing required field
- **THEN** the 422 response body contains `violations` with exactly two entries
- **AND** each entry has `loc`, `type`, `msg`, and `input` keys

#### Scenario: Same failure in production omits `input`

- **GIVEN** `APP_ENVIRONMENT=production`
- **WHEN** the client submits the same body as in the previous scenario
- **THEN** the 422 response body contains `violations` with exactly two entries
- **AND** each entry has `loc`, `type`, `msg` keys
- **AND** none of the entries contains an `input` key

#### Scenario: `loc` is preserved verbatim

- **GIVEN** a request whose nested field `body.address.zip` is invalid
- **WHEN** the 422 response is produced
- **THEN** one `violations` entry has `loc == ["body", "address", "zip"]`
