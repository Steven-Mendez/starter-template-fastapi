## Why

The current FastAPI + hexagonal implementation does not fully separate infrastructure failure semantics from application and HTTP semantics. This causes inconsistent error contracts (especially for persistence conflicts) and makes clients and operators unable to distinguish retriable technical failures from business rule violations.

## What Changes

- Introduce explicit application-level error categories for technical persistence failures and concurrency conflicts.
- Define a mandatory error translation boundary between outbound adapters and application use cases.
- Standardize API error mapping so equivalent failures always produce the same status code and response shape.
- Add observability requirements for translated failures (structured logs and stable error codes).
- **BREAKING**: API error codes/status values for selected failure paths will change to align with the new contract.

## Capabilities

### New Capabilities
- `error-boundary-and-translation`: Define normative requirements for translating infrastructure errors into stable application and HTTP contracts.

### Modified Capabilities
- None.

## Impact

- Affected code: application shared errors, persistence adapters, API error mappers, and endpoint behavior.
- Affected APIs: error payload semantics and status code matrix for selected endpoints.
- Affected systems: integration tests, monitoring dashboards, and any client logic depending on legacy error responses.
