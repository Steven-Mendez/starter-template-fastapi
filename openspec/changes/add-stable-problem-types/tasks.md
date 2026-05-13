## 1. ProblemType enum

- [ ] 1.1 Create `src/app_platform/api/problem_types.py` and define `class ProblemType(StrEnum)`.
- [ ] 1.2 Add canonical members with the URN values listed in `design.md`: `AUTH_INVALID_CREDENTIALS`, `AUTH_RATE_LIMITED`, `AUTH_TOKEN_STALE`, `AUTH_TOKEN_INVALID`, `AUTH_EMAIL_NOT_VERIFIED`, `AUTHZ_PERMISSION_DENIED`, `VALIDATION_FAILED`, `GENERIC_CONFLICT`, `GENERIC_NOT_FOUND`, `ABOUT_BLANK = "about:blank"`.

## 2. Wire through handlers

- [ ] 2.1 The existing `problem_json_response(...)` (`src/app_platform/api/error_handlers.py:41`) already takes `type_uri: str = "about:blank"` — pass `ProblemType.X` (which is `StrEnum`, so it's a `str` subclass) to that parameter at every call site. No signature change needed.
- [ ] 2.2 Update `src/features/authentication/adapters/inbound/http/errors.py`: `raise_http_from_auth_error` maps each `AuthError` subclass (via `isinstance`) to the matching `ProblemType` and passes it through to the HTTP exception.
- [ ] 2.3 Update `src/features/authorization/composition/wiring.py` so the 403 handler emits `ProblemType.AUTHZ_PERMISSION_DENIED`.
- [ ] 2.4 Update `src/app_platform/api/error_handlers.py` 422 handler to emit `ProblemType.VALIDATION_FAILED`.
- [ ] 2.5 Update `src/features/users/adapters/inbound/http/errors.py` to map `UserNotFoundError` → `ProblemType.GENERIC_NOT_FOUND` and `UserAlreadyExistsError` → `ProblemType.GENERIC_CONFLICT`.

## 3. Docs

- [ ] 3.1 Add a "Problem Type URNs" section to `docs/api.md` documenting the `urn:problem:<domain>:<code>` scheme and listing every member of `ProblemType` with its HTTP status code and the error class that produces it.

## 4. Tests

- [ ] 4.1 Per error class, write a test that hits the route and asserts `response.json()["type"]` matches the expected URN. One sub-test per URN:
  - [ ] 4.1.a `urn:problem:auth:invalid-credentials` (wrong password to `POST /auth/login`).
  - [ ] 4.1.b `urn:problem:auth:rate-limited` (trip the login limiter).
  - [ ] 4.1.c `urn:problem:auth:token-stale` (use a token whose `authz_version` is behind).
  - [ ] 4.1.d `urn:problem:auth:token-invalid` (malformed Bearer token).
  - [ ] 4.1.e `urn:problem:auth:email-not-verified` (login with an unverified account).
  - [ ] 4.1.f `urn:problem:authz:permission-denied` (non-admin hits `GET /admin/users`).
  - [ ] 4.1.g `urn:problem:validation:failed` (malformed PATCH `/me` body).
  - [ ] 4.1.h `urn:problem:generic:not-found` (route that returns `UserNotFoundError`).
  - [ ] 4.1.i `urn:problem:generic:conflict` (register duplicate email → `UserAlreadyExistsError`).
- [ ] 4.2 Add a test that asserts `ProblemType.ABOUT_BLANK == "about:blank"` and that an uncategorized exception still produces that value.

## 5. Wrap-up

- [ ] 5.1 Run `make ci` and confirm green.
