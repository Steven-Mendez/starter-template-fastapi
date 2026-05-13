## Why

No route declares `responses={401: ..., 403: ..., 422: ..., 429: ...}`. Generated OpenAPI shows only `200`/`201`/`204`, so SDK generators (openapi-typescript, openapi-python-client) can't surface error shapes. There is also no Pydantic `ProblemDetails` model and no `operationId` convention.

## What Changes

- Introduce a `ProblemDetails` Pydantic model (plus the supporting `Violation` model) in `src/app_platform/api/schemas.py` and use it both for serialization and as the response model declared per route.
- Build a `PROBLEM_RESPONSES` dict `{status_code: {"model": ProblemDetails, "content": {"application/problem+json": {...}}}}` in `src/app_platform/api/responses.py`, covering 400/401/403/404/409/422/429.
- Spread `**PROBLEM_RESPONSES` (or the relevant subset) into every route's `responses=` kwarg.
- Define an `operationId` convention `{router_name}_{handler_name}` in snake_case (e.g. `auth_login`, `users_patch_me`, `admin_list_users`). Apply via `generate_unique_id_function` on every `APIRouter`.

**Capabilities — Modified**: `project-layout`.

## Impact

- **Code (new)**:
  - `src/app_platform/api/responses.py` (defines `PROBLEM_RESPONSES` and per-feature subset constants).
- **Code (edit)**:
  - `src/app_platform/api/schemas.py` (adds `ProblemDetails` and `Violation` Pydantic models).
  - `src/features/authentication/adapters/inbound/http/auth.py` (route decorators carry `responses=` and `operation_id=...` or rely on `generate_unique_id_function`).
  - `src/features/authentication/adapters/inbound/http/admin.py` (same).
  - `src/features/users/adapters/inbound/http/me.py` (same).
  - `src/features/users/adapters/inbound/http/admin.py` (same).
  - `src/app_platform/api/root.py` (same, for `/health/*`).
  - `src/app_platform/api/app_factory.py` (install `generate_unique_id_function` on each `APIRouter`, or set it via the factory that constructs them).
  - `docs/api.md` (document the `operationId` convention and the `PROBLEM_RESPONSES` reuse).
- **OpenAPI**: SDK generators emit typed error branches.
- **Tests**: schema-presence assertion (`/openapi.json` contains the error responses and the `ProblemDetails` schema).
