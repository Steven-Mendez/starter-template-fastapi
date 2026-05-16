# API Reference

This document describes the HTTP API exposed by the current source code.
Every endpoint, request/response field, status code, response header,
error `code`, and Problem-Type `type` URN below is verifiable in
`src/features/*/adapters/inbound/http/` or `src/app_platform/api/`.

## Base URL

Local development default:

```text
http://localhost:8000
```

## Mounting and route prefixes

There is **no** app-level `/api` prefix. Each feature router carries its
own prefix and is mounted at the application root:

- The authentication feature mounts `build_auth_router()` via
  `mount_auth_routes(app)` (`src/main.py` →
  `src/features/authentication/composition/wiring.py`). It aggregates
  the `auth_router` (prefix `/auth`,
  `src/features/authentication/adapters/inbound/http/auth.py`) and the
  `admin_router` (prefix `/admin`,
  `src/features/authentication/adapters/inbound/http/admin.py`).
- The users feature mounts `build_users_router()` via
  `mount_users_routes(app)` (`src/main.py` →
  `src/features/users/composition/wiring.py`). It aggregates the
  `me_router` (no prefix — routes are `/me`, `/me/erase`, `/me/export`,
  `src/features/users/adapters/inbound/http/me.py`) and the
  `admin_router` (prefix `/admin`,
  `src/features/users/adapters/inbound/http/admin.py`).
- The platform `root_router` (`/`, `/health/live`, `/health/ready`) is
  included by `src/app_platform/api/app_factory.py`.

The only health routes are `GET /health/live` and `GET /health/ready`.
There is **no** `GET /health` route.

The `email`, `background_jobs`, `file_storage`, and `outbox` features
expose **no inbound HTTP routes**. They are reached through application
ports from the request path or the background worker, never over HTTP,
so they have no entries in this document.

## OpenAPI

When `APP_ENABLE_DOCS=true`, Swagger UI and ReDoc are available at:

- `/docs`
- `/redoc`

`/openapi.json` is disabled together with the interactive docs when
`APP_ENABLE_DOCS=false`.

### Operation IDs

Every route has a stable `operationId` produced by the convention
`{router_tag}_{handler_name}` in snake_case, where `router_tag` is the
router's first `tags` entry (or `root` if unset) and `handler_name` is
the snake_case Python name of the handler function (preserved by
FastAPI on `route.name`). The convention is implemented in
`src/app_platform/api/operation_ids.py` and installed on every
`APIRouter` via `generate_unique_id_function`.

Examples produced:

| Path | operationId |
| --- | --- |
| `POST /auth/login` | `auth_login` |
| `POST /auth/logout` | `auth_logout` |
| `GET /me` | `users_get_me` |
| `PATCH /me` | `users_patch_me` |
| `DELETE /me` | `users_delete_me` |
| `GET /admin/users` | `users_admin_list_users` |
| `GET /admin/audit-log` | `auth_admin_list_audit_events` |
| `GET /health/live` | `root_health_live` |

The OpenAPI schema-presence test under `src/features/authentication/tests/e2e/test_openapi_problem_details.py`
enforces the convention: every `operationId` must match
`^[a-z_]+_[a-z_]+$`, and no two operations may share the same ID.

### Reusable error-response constants

Every route's `responses=` dict is spread from a feature-scoped
constant defined in `src/app_platform/api/responses.py`:

| Constant | Status codes declared | Used by |
| --- | --- | --- |
| `AUTH_RESPONSES` | `401`, `403`, `409`, `422`, `429` | `/auth/*` routes |
| `USERS_RESPONSES` | `401`, `403`, `404`, `422` | `/me`, `/me/*` routes |
| `ADMIN_RESPONSES` | `400`, `401`, `403`, `404`, `422` | `/admin/*` routes |

Every entry references `ProblemDetails` (declared in
`src/app_platform/api/schemas.py`) as `application/problem+json`, so
generated SDKs emit a typed error branch for each declared status.
Add a new route by spreading the matching constant into its decorator,
e.g. `responses=USERS_RESPONSES`.

## Authentication

The service uses **JWT Bearer access tokens** plus an **httpOnly
refresh-token cookie**. There is no API-key mechanism.

### Access token (Bearer)

`POST /auth/login` and `POST /auth/refresh` return a `TokenResponse`
whose `access_token` is a signed JWT. Protected endpoints expect it in
the `Authorization` header:

```http
Authorization: Bearer <access_token>
```

The Bearer scheme is implemented by `HTTPBearer` in
`src/app_platform/api/authorization.py`; the principal is resolved
through `app.state.principal_resolver`. A missing, malformed, or stale
token returns `401` with a Problem Details body
(`urn:problem:auth:token-invalid` or `urn:problem:auth:token-stale`).

### Refresh-token cookie

On `POST /auth/login` and `POST /auth/refresh`, the refresh token is set
as a cookie (`src/features/authentication/adapters/inbound/http/auth.py`,
`_set_refresh_cookie`):

- name `refresh_token`
- `HttpOnly` (not readable by JavaScript)
- `Path=/auth` (only sent to `/auth/refresh` and `/auth/logout`)
- `Secure` and `SameSite` controlled by `APP_AUTH_COOKIE_SECURE` /
  `APP_AUTH_COOKIE_SAMESITE`
- `Max-Age` = `APP_AUTH_REFRESH_TOKEN_EXPIRE_DAYS` (in seconds)

`POST /auth/refresh`, `POST /auth/logout`, and `DELETE /me` clear the
cookie by emitting a matching `Set-Cookie: refresh_token=; Max-Age=0;
Path=/auth` (`clear_refresh_cookie` in
`src/features/authentication/adapters/inbound/http/cookies.py`).

`POST /auth/refresh` and `POST /auth/logout` additionally enforce a
CSRF origin check (`_enforce_cookie_origin`): a request that carries the
refresh cookie but presents no trusted `Origin`/`Referer` (per
`APP_CORS_ORIGINS`) is refused with `403 Untrusted origin`.

### Authorization (admin endpoints)

Admin routes add `require_authorization("<action>", "system", None)`
(`src/app_platform/api/authorization.py`), which resolves the Bearer
principal and then checks the relation on the `system:main` singleton
through the `AuthorizationPort`. A non-admin principal gets `403` with
`urn:problem:authz:permission-denied`.

## Common Response Headers

Every response includes `X-Request-ID`.

- If the request provides `X-Request-ID`, the response echoes it.
- If the request omits `X-Request-ID`, the middleware generates a UUID string.

`429` responses additionally carry a `Retry-After` header (seconds).
`POST /admin/users/{user_id}/erase` and `DELETE /me/erase` return a
`Location` header pointing at the erase-job status path. The degraded
`GET /health/ready` (`503` `{"status":"fail"}`) carries `Retry-After: 1`.

## Pagination

Admin list endpoints use **keyset pagination** rather than offsets, so
deep pages stay constant-time and remain correct under concurrent
inserts. The cursor is opaque to clients — treat it as a string and pass
it back unchanged.

### Cursor format

The cursor is the base64-URL-safe encoding of a tiny JSON payload:

```json
{"created_at": "2026-05-01T12:34:56+00:00", "id": "0192a3b4-..."}
```

Clients should not parse the cursor — the JSON shape may evolve. The
authoritative semantics are:

- A request with no cursor returns the first page.
- A response includes `next_cursor` (or `next_before` on the audit log)
  iff another page is available. The field is `null`/absent on the last
  page.
- Pass `next_cursor` back as `?cursor=<token>` to fetch the next page.
- Cursors that fail to decode return `400 Bad Request` (Problem Details)
  and no database query runs.

### Endpoints that paginate

| Endpoint | Query parameter | Response field |
| --- | --- | --- |
| `GET /admin/users` | `?cursor=<base64>` | `next_cursor` |
| `GET /admin/audit-log` | `?before=<base64>` | `next_before` (walks newest-first) |

Both endpoints accept a `?limit=<n>` parameter (default 100, range
1–500). Each page contains up to `limit` rows ordered by
`(created_at, id)` — ascending for `/admin/users`, descending for
`/admin/audit-log`.

## Error Format

Errors are rendered as `application/problem+json`.

Common fields:

| Field | Type | Description |
| --- | --- | --- |
| `type` | string | Stable Problem Type URN (see "Problem Type URNs" below), or `about:blank` for genuinely uncategorized errors. |
| `title` | string | HTTP status phrase or explicit validation title. |
| `status` | integer | HTTP status code. |
| `instance` | string | Request URL. |
| `detail` | string | Human-readable detail when available. |
| `request_id` | string | Request ID from middleware when available. |
| `code` | string | Application error code for application-level errors. |
| `violations` | array | Field-level validation failures for 422 responses; see "Violation shape" below. |

### Problem Type URNs

Per RFC 9457 §3.1, the `type` field SHOULD be a stable identifier that
clients can branch on without parsing the human-readable `detail`. This
service uses a project-scoped URN scheme:

```text
urn:problem:<domain>:<code>
```

where `<domain>` is a lower-kebab capability tag (`auth`, `authz`,
`validation`, `generic`) and `<code>` is a lower-kebab error slug. URN
values are stable across versions — new members may be added but
existing values are never renamed. `about:blank` remains the
spec-compliant fallback for genuinely uncategorized errors.

The canonical catalog is defined as the `ProblemType` enum in
`src/app_platform/api/problem_types.py`:

| URN | HTTP status | Produced by |
| --- | --- | --- |
| `urn:problem:auth:invalid-credentials` | `401` | `InvalidCredentialsError` (wrong password / unknown email on login or self-erase re-auth). |
| `urn:problem:auth:rate-limited` | `429` | `RateLimitExceededError` (login/register/password-reset throttling). |
| `urn:problem:auth:token-stale` | `401` | `StaleTokenError` (access token's `authz_version` is behind the current value — re-authenticate). |
| `urn:problem:auth:token-invalid` | `401` / `400` | `InvalidTokenError` (malformed/expired Bearer token) and `TokenAlreadyUsedError` (one-shot reset/verification token already consumed). |
| `urn:problem:auth:email-not-verified` | `403` | `EmailNotVerifiedError` (login attempt when verification is required). |
| `urn:problem:authz:permission-denied` | `403` | `NotAuthorizedError`, `PermissionDeniedError`, `InactiveUserError` (principal lacks the required relation on the resource, or account is inactive). |
| `urn:problem:validation:failed` | `422` | FastAPI `RequestValidationError` (malformed request body / query / path). |
| `urn:problem:generic:conflict` | `409` | `UserAlreadyExistsError`, `DuplicateEmailError`, `ConflictError`. |
| `urn:problem:generic:not-found` | `404` | `UserNotFoundError`, `NotFoundError`. |
| `about:blank` | varies | Genuinely uncategorized failures (configuration errors, unhandled exceptions, malformed cursors, internal 500s). |

### Violation shape (422 responses)

A `422 Unprocessable Content` response always carries a `violations`
array on the Problem Details body — one entry per failed field. This is
the RFC 9457 §3.1 "extension member" convention adapted to this
service's terminology (`violations` rather than `invalid_params`).

| Field | Type | Description |
| --- | --- | --- |
| `loc` | `list[str \| int]` | Canonical Pydantic location path for the failed field, preserving order and types (e.g. `["body", "address", "zip"]`, `["query", "limit"]`). SDKs use this to route the failure back to the right form field. |
| `type` | `string` | Stable Pydantic error type (e.g. `missing`, `value_error`, `string_too_short`). Treat as a public contract — new types may appear, existing types are not renamed. |
| `msg` | `string` | Human-readable explanation. |
| `input` | `object \| null` | The offending input value. **Present only in non-production environments.** Omitted (key absent) when `APP_ENVIRONMENT=production` to avoid echoing secrets. |

The `loc`, `type`, and `msg` fields are identical across environments;
only `input` is environment-gated. Producers MUST treat `input` as a
debug aid — the same redaction rules used for log scrubbing apply when
it enters logs.

Example 422 body (development):

```json
{
  "type": "urn:problem:validation:failed",
  "title": "Unprocessable Content",
  "status": 422,
  "instance": "http://localhost:8000/me",
  "detail": "Validation failed: 2 field(s)",
  "request_id": "abc-123",
  "violations": [
    {
      "loc": ["body", "email"],
      "type": "value_error",
      "msg": "value is not a valid email address",
      "input": "not-an-email"
    },
    {
      "loc": ["body", "name"],
      "type": "missing",
      "msg": "Field required",
      "input": null
    }
  ]
}
```

In production, each entry contains only `loc`, `type`, and `msg`.

### Example application error

A wrong-password `POST /auth/login` raises `InvalidCredentialsError`,
which `raise_http_from_auth_error`
(`src/features/authentication/adapters/inbound/http/errors.py`) maps to
`401` with `code=invalid_credentials` and
`type=urn:problem:auth:invalid-credentials`:

```json
{
  "type": "urn:problem:auth:invalid-credentials",
  "title": "Unauthorized",
  "status": 401,
  "instance": "http://localhost:8000/auth/login",
  "detail": "Invalid credentials",
  "code": "invalid_credentials",
  "request_id": "abc-123"
}
```

A non-admin principal calling `GET /admin/users` is rejected by
`require_authorization` with `403`, `code=permission_denied`,
`type=urn:problem:authz:permission-denied`:

```json
{
  "type": "urn:problem:authz:permission-denied",
  "title": "Forbidden",
  "status": 403,
  "instance": "http://localhost:8000/admin/users",
  "detail": "Permission denied",
  "code": "permission_denied",
  "request_id": "abc-123"
}
```

## Status Codes

| Status | Meaning |
| --- | --- |
| `200` | Successful read / login / refresh / logout / patch, or a ready `/health/ready` / liveness response. |
| `201` | User created (`POST /auth/register`). |
| `202` | Accepted-for-async: `POST /auth/password/forgot`, `POST /auth/email/verify/request`, `DELETE /me/erase`, `POST /admin/users/{user_id}/erase`. |
| `204` | `DELETE /me` (self-deactivation), no body. |
| `400` | Malformed pagination cursor (`?cursor=`/`?before=`), or a one-shot token already consumed (`TokenAlreadyUsedError`). |
| `401` | Missing/invalid/stale Bearer token, wrong credentials on `POST /auth/login`, or wrong password on `DELETE /me/erase` re-auth. |
| `403` | Authenticated but not authorized (non-admin on an `/admin/*` route, inactive account, unverified email on login, or an untrusted origin on a refresh-cookie request). |
| `404` | User/record not found (`UserNotFoundError` / `NotFoundError`). |
| `409` | Email already registered (`DuplicateEmailError` / `UserAlreadyExistsError` / `ConflictError`). |
| `422` | Request body / query / path validation failed (carries `violations`). |
| `429` | Auth rate limit exceeded (carries `Retry-After`). |
| `500` | Unmapped domain error or unhandled server error. |
| `503` | Principal resolver / authorization port / erase / export pipeline not wired, auth not configured, or `/health/ready` not yet ready / degraded. |

Path IDs (e.g. `{user_id}`) are parsed as UUIDs by FastAPI. Invalid
UUID path values return `422`.

## Schemas

Audited from
`src/features/authentication/adapters/inbound/http/schemas.py` and
`src/features/users/adapters/inbound/http/schemas.py`.

### RegisterRequest

Body of `POST /auth/register`.

| Field | Type | Required | Validation |
| --- | --- | --- | --- |
| `email` | string | yes | Length 3–254; normalized; must contain `@`. |
| `password` | string | yes | Length 12–256; ≥ 3 of {upper, lower, digit, symbol} or length ≥ 20. |

### LoginRequest

Body of `POST /auth/login`.

| Field | Type | Required | Validation |
| --- | --- | --- | --- |
| `email` | string | yes | Length 3–254; normalized. |
| `password` | string | yes | Length 1–256. |

### PasswordForgotRequest

Body of `POST /auth/password/forgot`.

| Field | Type | Required | Validation |
| --- | --- | --- | --- |
| `email` | string | yes | Length 3–254; normalized. |

### PasswordResetRequest

Body of `POST /auth/password/reset`.

| Field | Type | Required | Validation |
| --- | --- | --- | --- |
| `token` | string | yes | Length 32–512. |
| `new_password` | string | yes | Length 12–256; same complexity rule as `RegisterRequest.password`. |

### EmailVerifyRequest

Body of `POST /auth/email/verify`.

| Field | Type | Required | Validation |
| --- | --- | --- | --- |
| `token` | string | yes | Length 32–512. |

### UserPublic (authentication)

Returned by `POST /auth/register`.

| Field | Type |
| --- | --- |
| `id` | UUID |
| `email` | string |
| `is_active` | boolean |
| `is_verified` | boolean |
| `authz_version` | integer |
| `created_at` | datetime |
| `updated_at` | datetime |
| `last_login_at` | datetime or null |

### UserPublic (users)

Returned in `UserListPage.items` from `GET /admin/users`.

| Field | Type |
| --- | --- |
| `id` | UUID |
| `email` | string |
| `is_active` | boolean |
| `is_verified` | boolean |
| `authz_version` | integer |
| `created_at` | datetime |
| `updated_at` | datetime |

### UserPublicSelf

Returned by `GET /me` and `PATCH /me`.

| Field | Type |
| --- | --- |
| `id` | UUID |
| `email` | string |
| `is_active` | boolean |
| `is_verified` | boolean |
| `created_at` | datetime |
| `updated_at` | datetime |

### PrincipalPublic

Returned by `GET /auth/me`, and nested as `TokenResponse.user`.

| Field | Type |
| --- | --- |
| `id` | UUID |
| `email` | string |
| `is_active` | boolean |
| `is_verified` | boolean |

### TokenResponse

Returned by `POST /auth/login` and `POST /auth/refresh`.

| Field | Type |
| --- | --- |
| `access_token` | string (JWT) |
| `token_type` | string (`"bearer"`) |
| `expires_in` | integer (seconds) |
| `user` | `PrincipalPublic` |

### MessageResponse

| Field | Type |
| --- | --- |
| `message` | string |

### InternalTokenResponse

Returned by `POST /auth/password/forgot` and
`POST /auth/email/verify/request`. `dev_token` is `null` in production;
it is populated only when `APP_AUTH_RETURN_INTERNAL_TOKENS=true`.

| Field | Type |
| --- | --- |
| `message` | string |
| `dev_token` | string or null |
| `expires_at` | datetime or null |

### AuditEventRead

| Field | Type |
| --- | --- |
| `id` | UUID |
| `user_id` | UUID or null |
| `event_type` | string |
| `metadata` | object |
| `created_at` | datetime |

### AuditLogRead

Returned by `GET /admin/audit-log`.

| Field | Type |
| --- | --- |
| `items` | array of `AuditEventRead` |
| `count` | integer |
| `limit` | integer |
| `next_before` | string or null |

### UpdateProfileRequest

Body of `PATCH /me`.

| Field | Type | Required |
| --- | --- | --- |
| `email` | string or null | no |

### UserListPage

Returned by `GET /admin/users`.

| Field | Type |
| --- | --- |
| `items` | array of `UserPublic` (users variant) |
| `count` | integer |
| `limit` | integer |
| `next_cursor` | string or null |

### EraseSelfRequest

Body of `DELETE /me/erase` (password re-auth).

| Field | Type | Required |
| --- | --- | --- |
| `password` | string | yes |

### ErasureAccepted

Returned by `DELETE /me/erase` and
`POST /admin/users/{user_id}/erase`.

| Field | Type |
| --- | --- |
| `status` | string (`"accepted"`) |
| `job_id` | string |
| `estimated_completion_seconds` | integer |

### ExportResponse

Returned by `GET /me/export` and
`GET /admin/users/{user_id}/export`.

| Field | Type |
| --- | --- |
| `download_url` | string |
| `expires_at` | datetime |

### Self-view vs admin-view user schemas

`GET /me` and `PATCH /me` respond with `UserPublicSelf`. `GET /admin/users`
responds with `UserPublic` (users variant). The two schemas are
intentionally distinct so that internal bookkeeping fields a user
should not see about themselves never appear on self-views.

The redacted field set on self-views — the exhaustive list of fields
present on `UserPublic` and removed from `UserPublicSelf` — is:

- `authz_version` — internal ReBAC cache-invalidation counter. Returning
  it on `/me` would leak permission-change history to the user (a role
  granted then revoked manifests as a bumped counter). Admin views keep
  the field because operators need it for cache reasoning.

All other fields (`id`, `email`, `is_active`, `is_verified`,
`created_at`, `updated_at`) are present on both schemas. A unit test
pins the symmetric difference of the two schemas' `model_fields` to
exactly `{"authz_version"}` so any future addition to either schema
forces a deliberate decision about which view it belongs on.

## Endpoints

### GET /

Returns a static heartbeat payload identifying the service.

Response `200`:

```json
{
  "name": "starter-template-fastapi",
  "message": "FastAPI service is running."
}
```

### GET /health/live

Process liveness. Does not check external dependencies.

Response `200`:

```json
{
  "status": "ok"
}
```

### GET /health/ready

Readiness probe. While the lifespan has not finished starting up the
probe short-circuits without touching any dependency.

Response `503` during startup (no `Retry-After` — kubelet's own backoff
is sufficient):

```json
{
  "status": "starting"
}
```

Response `200` when ready and every configured dependency responds
within its timeout (`deps` is keyed by dependency name — `db`, and
`redis`/`s3` when configured — each value `"ok"`):

```json
{
  "status": "ok",
  "deps": {
    "db": "ok"
  }
}
```

Response `503` with a `Retry-After: 1` header when any probe times out
or raises (failing dependencies carry `{"status":"fail","reason":"…"}`):

```json
{
  "status": "fail",
  "deps": {
    "db": {
      "status": "fail",
      "reason": "timeout"
    }
  }
}
```

### POST /auth/register

Auth: none (rate-limited per IP and per target email).

Request: `RegisterRequest`.

Response `201`: `UserPublic` (authentication variant).

Errors: `409` `code=duplicate_email` when the email already exists;
`422` on validation failure; `429` when rate-limited.

### POST /auth/login

Auth: none (rate-limited per (IP, email) and per account).

Request: `LoginRequest`.

Response `200`: `TokenResponse`, and a `Set-Cookie: refresh_token=…;
HttpOnly; Path=/auth` header.

Errors: `401` `code=invalid_credentials` on wrong email/password; `403`
`code=email_not_verified` when verification is required; `429` when
rate-limited.

### POST /auth/refresh

Auth: refresh cookie + origin check.

Request body: none — the refresh token is read from the `refresh_token`
cookie.

Response `200`: `TokenResponse` plus a rotated refresh cookie.

Errors: `401` `code=invalid_token` when the cookie is missing/invalid;
`403 Untrusted origin` when the CSRF origin check fails.

### POST /auth/logout

Auth: refresh cookie + origin check.

Request body: none.

Response `200`: `MessageResponse` (`{"message":"Logged out"}`), and the
refresh cookie is cleared (`Set-Cookie: refresh_token=; Max-Age=0;
Path=/auth`).

Errors: `403 Untrusted origin` when the CSRF origin check fails.

### POST /auth/logout-all

Auth: Bearer.

Request body: none.

Response `200`: `MessageResponse` (`{"message":"All sessions
revoked"}`); the refresh cookie is cleared.

Errors: `401` when the Bearer token is missing/invalid.

### GET /auth/me

Auth: Bearer.

Response `200`: `PrincipalPublic`.

Errors: `401` when the Bearer token is missing/invalid.

### POST /auth/password/forgot

Auth: none (rate-limited per (IP, email) and per account).

Request: `PasswordForgotRequest`.

Response `202`: `InternalTokenResponse`. The response is identical
whether or not the account exists (anti-enumeration).

Errors: `429` when rate-limited.

### POST /auth/password/reset

Auth: none (rate-limited on a SHA-256 prefix of the token).

Request: `PasswordResetRequest`.

Response `200`: `MessageResponse` (`{"message":"Password reset
complete"}`). All existing sessions are revoked on success.

Errors: `400` `code=token_already_used` for a consumed token; `401`
`code=invalid_token` for an unknown token; `422` on validation failure;
`429` when rate-limited.

### POST /auth/email/verify/request

Auth: Bearer (rate-limited per user).

Request body: none.

Response `202`: `InternalTokenResponse`.

Errors: `401` when the Bearer token is missing/invalid; `429` when
rate-limited.

### POST /auth/email/verify

Auth: none.

Request: `EmailVerifyRequest`.

Response `200`: `MessageResponse` (`{"message":"Email verified"}`).

Errors: `400` `code=token_already_used` for a consumed token; `401`
`code=invalid_token` for an unknown token; `422` on validation failure.

### GET /admin/audit-log

Auth: Bearer + `require_authorization("read_audit", "system", None)`.

Query parameters: `user_id?` (UUID), `event_type?` (string, 1–150),
`since?` (datetime), `before?` (opaque cursor), `limit` (integer,
1–500, default 100).

Response `200`: `AuditLogRead`, newest-first, keyset-paginated via
`?before=` / `next_before`.

Errors: `400` for a malformed `before` cursor; `403`
`code=permission_denied` for a non-admin principal; `401` when the
Bearer token is missing/invalid.

### GET /me

Auth: Bearer.

Response `200`: `UserPublicSelf`.

Errors: `401` when the Bearer token is missing/invalid; `404`
`code=user_not_found` when the record is gone.

### PATCH /me

Auth: Bearer.

Request: `UpdateProfileRequest` (currently only `email`).

Response `200`: `UserPublicSelf`.

Errors: `401`; `404` `code=user_not_found`; `409`
`code=user_already_exists` if the new email is taken; `422` on
validation failure.

### DELETE /me

Auth: Bearer.

Deactivates the calling user's own account (soft delete). In a single
response cycle the server revokes every server-side refresh-token family
for the user (inside the same Unit of Work that flips
`is_active=False`) and clears the browser-side refresh cookie
(`Set-Cookie: refresh_token=; Max-Age=0; Path=/auth`). A subsequent
`POST /auth/refresh` with a captured refresh token returns `401`.

Response `204`: no body.

Errors: `401` when the Bearer token is missing/invalid; `404`
`code=user_not_found` when the record is already gone.

### DELETE /me/erase

Auth: Bearer + password re-authentication (GDPR Art. 17 self-erase).

Request: `EraseSelfRequest` (the caller's current password). A stolen
access token alone cannot erase the account.

Response `202`: `ErasureAccepted`, plus a `Location` header pointing at
the erase-job status path. The actual scrub runs asynchronously in the
worker.

Errors: `401` `code=invalid_credentials` when the password is wrong;
`503` `code=erasure_pipeline_unwired` when the erase pipeline is not
composed.

### GET /me/export

Auth: Bearer (GDPR Art. 15 self-export).

Response `200`: `ExportResponse` (`download_url` + `expires_at`). The
download URL points at a JSON blob the client fetches before
`expires_at`.

Errors: `401` when the Bearer token is missing/invalid; `503`
`code=export_pipeline_unwired` when the export pipeline is not composed.

### GET /admin/users

Auth: Bearer + `require_authorization("manage_users", "system", None)`.

Query parameters: `cursor?` (opaque cursor), `limit` (integer, 1–500,
default 100).

Response `200`: `UserListPage`, keyset-paginated via `?cursor=` /
`next_cursor`.

Errors: `400` `code=invalid_cursor` for a malformed cursor; `403`
`code=permission_denied` for a non-admin principal; `401` when the
Bearer token is missing/invalid.

### POST /admin/users/{user_id}/erase

Auth: Bearer + `require_authorization("manage_users", "system", None)`.

Path parameter: `user_id` (UUID). No password re-auth — the admin's
session is the audit trail.

Response `202`: `ErasureAccepted`, plus a `Location` header pointing at
the erase-job status path.

Errors: `403` `code=permission_denied` for a non-admin principal;
`401` when the Bearer token is missing/invalid; `503`
`code=erasure_pipeline_unwired` when the erase pipeline is not composed.

### GET /admin/users/{user_id}/export

Auth: Bearer + `require_authorization("manage_users", "system", None)`.

Path parameter: `user_id` (UUID).

Response `200`: `ExportResponse` (same shape as `GET /me/export`).

Errors: `403` `code=permission_denied` for a non-admin principal;
`401` when the Bearer token is missing/invalid; `503`
`code=export_pipeline_unwired` when the export pipeline is not composed.

## Curl Examples

Register a user:

```bash
curl -s -X POST http://localhost:8000/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"alice@example.com","password":"correct horse battery staple"}'
```

Log in (capture the access token; the refresh cookie is set on the
response):

```bash
curl -s -X POST http://localhost:8000/auth/login \
  -H 'Content-Type: application/json' \
  -c cookies.txt \
  -d '{"email":"alice@example.com","password":"correct horse battery staple"}'
```

Call a Bearer-protected endpoint with the returned `access_token`:

```bash
curl -s http://localhost:8000/me \
  -H 'Authorization: Bearer <access_token>'
```

Rotate the refresh token using the stored cookie (origin-checked):

```bash
curl -s -X POST http://localhost:8000/auth/refresh \
  -H 'Origin: http://localhost:8000' \
  -b cookies.txt -c cookies.txt
```
