## 1. ProblemDetails model + responses dict

- [ ] 1.1 In `src/app_platform/api/schemas.py`, define `class Violation(BaseModel)` with `loc: list[str | int]`, `type: str`, `msg: str`, `input: object | None = None`.
- [ ] 1.2 In the same file, define `class ProblemDetails(BaseModel)` with `type: str`, `title: str`, `status: int`, `detail: str | None = None`, `instance: str | None = None`, `violations: list[Violation] | None = None`. Document `type` as a URN drawn from `ProblemType`.
- [ ] 1.3 Create `src/app_platform/api/responses.py` and define `PROBLEM_RESPONSES: dict[int, dict]` with entries for 400, 401, 403, 404, 409, 422, 429; every entry uses `{"model": ProblemDetails, "content": {"application/problem+json": {"schema": ProblemDetails.model_json_schema()}}}` (or equivalent FastAPI form).
- [ ] 1.4 In the same file, export per-feature subsets: `AUTH_RESPONSES = {401: ..., 422: ..., 429: ...}`, `USERS_RESPONSES = {401: ..., 403: ..., 404: ..., 422: ...}`, `ADMIN_RESPONSES = {401: ..., 403: ..., 422: ...}`.

## 2. Apply per route

- [ ] 2.1 Add `responses=AUTH_RESPONSES` to every route decorator in `src/features/authentication/adapters/inbound/http/auth.py`.
- [ ] 2.2 Add `responses=USERS_RESPONSES` to every route in `src/features/users/adapters/inbound/http/me.py`.
- [ ] 2.3 Add `responses=ADMIN_RESPONSES` to every route in `src/features/users/adapters/inbound/http/admin.py` and `src/features/authentication/adapters/inbound/http/admin.py`.
- [ ] 2.4 Add the appropriate subset to every other route exposed by the application (`/health/*`, root).

## 3. operationId convention

- [ ] 3.1 Define a helper `def feature_operation_id(route) -> str: return f"{route.tags[0] if route.tags else 'root'}_{route.name}"` in `src/app_platform/api/app_factory.py` (or a small new utility module imported by it).
- [ ] 3.2 Install `generate_unique_id_function=feature_operation_id` on every `APIRouter` instantiation:
  - [ ] 3.2.a `src/features/authentication/adapters/inbound/http/auth.py` (`auth_router`)
  - [ ] 3.2.b `src/features/authentication/adapters/inbound/http/admin.py` (`admin_router`)
  - [ ] 3.2.c `src/features/authentication/adapters/inbound/http/router.py` (`build_auth_router`)
  - [ ] 3.2.d `src/features/users/adapters/inbound/http/me.py` (`me_router`)
  - [ ] 3.2.e `src/features/users/adapters/inbound/http/admin.py` (`admin_router`)
  - [ ] 3.2.f `src/features/users/adapters/inbound/http/router.py` (`build_users_router`)
  - [ ] 3.2.g `src/app_platform/api/root.py` (`root_router`)
- [ ] 3.3 Verify the produced IDs (`auth_login`, `auth_logout`, `users_get_me`, `users_patch_me`, `users_delete_me`, `users_admin_list_users`, `auth_admin_list_audit_events`, `root_health_live`, `root_health_ready`).

## 4. Tests

- [ ] 4.1 Add `src/app_platform/tests/e2e/test_openapi_problem_details.py` that fetches `/openapi.json` and asserts: every documented path has at least the 4xx responses declared in its feature's response subset; `components.schemas` contains both `ProblemDetails` and `Violation`.
- [ ] 4.2 Add a test that asserts every `operationId` in `/openapi.json` matches the regex `^[a-z_]+_[a-z_]+$` and that no two operations share the same `operationId`.

## 5. Docs

- [ ] 5.1 Document the `operationId` convention (`{router_tag}_{handler_name}` snake_case) and the per-feature `*_RESPONSES` constants in `docs/api.md`.

## 6. Wrap-up

- [ ] 6.1 Run `make ci` and confirm green.
