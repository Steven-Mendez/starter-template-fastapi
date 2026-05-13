## Why

Every error path sends `type: "about:blank"` (`src/app_platform/api/error_handlers.py`, `src/features/authorization/composition/wiring.py`, `src/features/authentication/adapters/inbound/http/errors.py`). RFC 9457 §3.1 recommends `about:blank` *only* when no specific type exists. The template has well-defined error cases (`invalid_credentials`, `rate_limit_exceeded`, `permission_denied`, `stale_token`, `validation_failed`) — SDKs would branch on stable `type` URNs but instead must parse `detail`.

## What Changes

- Define a `ProblemType(StrEnum)` mapping each domain error class to a stable URN of the form `urn:problem:<domain>:<code>` (e.g. `urn:problem:auth:invalid-credentials`).
- Pass it through `raise_http_from_auth_error` and the generic handlers; emit it as the `type` field of the Problem Details body.
- Document the URN scheme and the complete catalog in `docs/api.md`.

**Capabilities — Modified**: `project-layout`.

## Impact

- **Code (new)**:
  - `src/app_platform/api/problem_types.py` (defines `ProblemType(StrEnum)` and the canonical catalog).
- **Code (edit)**:
  - `src/app_platform/api/error_handlers.py` (every `JSONResponse({...})` call sets `type` from `ProblemType` rather than the literal `"about:blank"`).
  - `src/features/authentication/adapters/inbound/http/errors.py` (`raise_http_from_auth_error` passes the matching `ProblemType` through to the HTTP exception).
  - `src/features/authorization/composition/wiring.py` (authz 403 handler uses `ProblemType.AUTHZ_PERMISSION_DENIED`).
  - `src/features/users/adapters/inbound/http/errors.py` (users-feature mapping picks the matching `ProblemType`).
  - `docs/api.md` (URN scheme section + catalog table).
- **Backwards compatibility**: clients that did NOT parse `type` are unaffected. Clients that branched on `about:blank` continue to work (we still emit it for genuinely uncategorized cases).
- **Tests**: assertion per error path that the right URN appears.
