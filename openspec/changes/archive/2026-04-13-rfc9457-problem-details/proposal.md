## Why

HTTP APIs should return machine-readable, consistent error bodies. [RFC 9457](https://www.rfc-editor.org/rfc/rfc9457) (Problem Details for HTTP APIs) defines `application/problem+json` and a small set of core members (`type`, `title`, `status`, `detail`, `instance`) so clients can handle failures uniformly.

## What Changes

- Add a shared error response model and global exception handlers so 4xx/5xx responses from this service use `application/problem+json` and RFC 9457 semantics.
- Map `HTTPException` and request validation failures (`RequestValidationError`) to Problem Details, preserving validation error payloads in an extension member where useful.
- Document the behavior in an OpenSpec capability and verify it with integration tests.

## Capabilities

### New Capabilities

- `rfc9457`: Problem Details media type and JSON shape for error responses.

### Modified Capabilities

- None (orthogonal to existing Kanban API behavior; status codes stay the same).

## Impact

- **Code**: New module for Problem Details + registration on the FastAPI app; `main.py` wires handlers.
- **Tests**: Integration tests assert media type and required JSON members for representative errors.
- **Clients**: Error bodies change from ad hoc FastAPI `{"detail": ...}` to RFC 9457-shaped documents (with `detail` as the RFC field name).
