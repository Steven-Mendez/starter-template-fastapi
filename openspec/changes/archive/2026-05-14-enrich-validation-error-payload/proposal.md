## Why

`src/app_platform/api/error_handlers.py`: in non-production the 422 handler dumps raw `exc.errors()` (Pydantic-shaped, leaks internal `loc` tuples and `ctx`); in production it strips them entirely. Neither matches RFC 9457's `invalid_params` convention. Clients cannot programmatically map field-level errors back to form fields.

## What Changes

- Always emit a stable `violations: list[Violation]` field on the 422 Problem Details body, with one `Violation` per failed field.
- `Violation` shape: `loc: list[str | int]`, `type: str` (Pydantic error type), `msg: str`, `input: object | None` (present in dev, omitted in production).
- Same shape in production and non-production. Production omits only the `input` field; `loc`, `type`, and `msg` are identical.

**Capabilities — Modified**: `project-layout`.

## Impact

- **Code (edit)**:
  - `src/app_platform/api/error_handlers.py` (add `pydantic_errors_to_violations` helper; replace dev/prod branching with a single call that always produces `violations`).
  - `docs/api.md` (document the `Violation` shape next to the Problem Type URN catalog).
- **Tests**: validation-failure scenarios assert the right `violations` array (including in production mode, which omits `input` but keeps `loc`/`type`/`msg`).
