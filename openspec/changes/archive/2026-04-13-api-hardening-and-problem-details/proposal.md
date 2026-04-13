## Why

The API currently has minimal production hardening and coarse error mapping, which can confuse clients and reduce operational safety. We need explicit middleware/security defaults and more accurate Problem Details behavior.

## What Changes

- Introduce configurable CORS and trusted-host middleware behavior for non-local environments.
- Add request correlation logging middleware to improve traceability.
- Refine domain-error-to-HTTP mapping so business-rule failures do not collapse into 404.
- Extend Problem Details consistency for unhandled exceptions while preserving RFC 9457 response shape.
- Make docs endpoint exposure environment-aware.

## Capabilities

### New Capabilities
- `api-security-middleware`: Define baseline CORS and host-header protections as configurable middleware.
- `request-correlation-logging`: Attach and emit request identifiers for traceable request/response flows.

### Modified Capabilities
- `rfc9457`: Expand problem-details behavior for additional error classes and stable error typing.
- `api-core`: Make interactive docs availability controlled by runtime configuration.

## Impact

- Affected files: `main.py`, `problem_details.py`, `kanban/router.py`, settings module(s), and integration tests.
- May introduce new settings dependencies and additional middleware execution per request.
- Changes response semantics for selected error classes; integration contracts must be updated.
