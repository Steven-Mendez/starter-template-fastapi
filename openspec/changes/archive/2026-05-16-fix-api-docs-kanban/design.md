# Design

## Context

`docs/api.md` describes a Kanban service. The repository is a
feature-first FastAPI starter with six real features and a platform
layer; it has never had Kanban routes. The document is therefore not
"stale" — it is wholly fictional and actively misleading. The job is to
replace it with a document that is true to the code, derived only from
the inbound HTTP layer, with the good structural sections preserved
where they already describe real platform behavior.

## Goal

Every endpoint, payload field, status code, header, and error code in
`docs/api.md` must be verifiable by grepping the source. No documented
behavior may exist only in the doc.

## The authoritative route inventory (audited from code)

This is the verified surface. Every row was read out of the cited file
in this change's investigation. The implementer MUST re-derive it from
the code (the verification gate in `tasks.md`), not copy it blindly —
but this is the expected result.

### Public auth — `src/features/authentication/adapters/inbound/http/auth.py` (router prefix `/auth`)

| Method & path | Auth | Request body | Success | Source symbol |
|---|---|---|---|---|
| `POST /auth/register` | none (rate-limited) | `RegisterRequest` | `201` `UserPublic` (auth) | `register` |
| `POST /auth/login` | none (rate-limited) | `LoginRequest` | `200` `TokenResponse` + `Set-Cookie: refresh_token` | `login` |
| `POST /auth/refresh` | refresh cookie + origin check | none (cookie) | `200` `TokenResponse` + rotated cookie | `refresh` |
| `POST /auth/logout` | refresh cookie + origin check | none (cookie) | `200` `MessageResponse`, cookie cleared | `logout` |
| `POST /auth/logout-all` | Bearer | none | `200` `MessageResponse`, cookie cleared | `logout_all` |
| `GET /auth/me` | Bearer | — | `200` `PrincipalPublic` | `me` |
| `POST /auth/password/forgot` | none (rate-limited) | `PasswordForgotRequest` | `202` `InternalTokenResponse` | `forgot_password` |
| `POST /auth/password/reset` | none (rate-limited on token hash) | `PasswordResetRequest` | `200` `MessageResponse` | `reset_password` |
| `POST /auth/email/verify/request` | Bearer (rate-limited) | none | `202` `InternalTokenResponse` | `request_email_verify` |
| `POST /auth/email/verify` | none | `EmailVerifyRequest` | `200` `MessageResponse` | `verify_email` |

### Admin auth — `src/features/authentication/adapters/inbound/http/admin.py` (router prefix `/admin`)

| Method & path | Auth | Query | Success | Source symbol |
|---|---|---|---|---|
| `GET /admin/audit-log` | Bearer + `require_authorization("read_audit", "system", None)` | `user_id?`, `event_type?`, `since?`, `before?`, `limit` (1–500, default 100) | `200` `AuditLogRead` | `admin_list_audit_events` |

### Users self — `src/features/users/adapters/inbound/http/me.py`

| Method & path | Auth | Request body | Success | Source symbol |
|---|---|---|---|---|
| `GET /me` | Bearer | — | `200` `UserPublicSelf` | `get_me` |
| `PATCH /me` | Bearer | `UpdateProfileRequest` | `200` `UserPublicSelf` | `patch_me` |
| `DELETE /me` | Bearer | — | `204` (cookie cleared) | `delete_me` |
| `DELETE /me/erase` | Bearer + password re-auth | `EraseSelfRequest` | `202` `ErasureAccepted` + `Location` | `erase_me` |
| `GET /me/export` | Bearer | — | `200` `ExportResponse` | `export_me` |

### Users admin — `src/features/users/adapters/inbound/http/admin.py` (router prefix `/admin`)

| Method & path | Auth | Query / path | Success | Source symbol |
|---|---|---|---|---|
| `GET /admin/users` | Bearer + `require_authorization("manage_users", "system", None)` | `cursor?`, `limit` (1–500, default 100) | `200` `UserListPage` | `admin_list_users` |
| `POST /admin/users/{user_id}/erase` | Bearer + `manage_users` | path `user_id` | `202` `ErasureAccepted` + `Location` | `admin_erase_user` |
| `GET /admin/users/{user_id}/export` | Bearer + `manage_users` | path `user_id` | `200` `ExportResponse` | `admin_export_user` |

### Platform — `src/app_platform/api/root.py`, `src/app_platform/api/health.py`

| Method & path | Auth | Success | Source symbol |
|---|---|---|---|
| `GET /` | none | `200` `{"name","message"}` | `read_root` |
| `GET /health/live` | none | `200` `{"status":"ok"}` | `health_live` |
| `GET /health/ready` | none | `200` `{"status":"ok","deps":{…}}` / `503` `{"status":"starting"}` / `503` `{"status":"fail","deps":{…}}`+`Retry-After:1` | `health_ready` |

No app-level `/api` prefix exists: `src/main.py` calls
`mount_auth_routes` / `mount_users_routes`, which do
`app.include_router(build_auth_router())` /
`app.include_router(build_users_router())`; the `/auth` and `/admin`
prefixes come from the feature `APIRouter`s themselves. `root_router`
(`/`, `/health/live`, `/health/ready`) is included by
`src/app_platform/api/app_factory.py`. There is **no** `GET /health`
route — the only health paths are `/health/live` and `/health/ready`.

`email`, `background_jobs`, `file_storage`, and `outbox` have **no
inbound HTTP routers** (`src/features/<f>/adapters/inbound/http/` either
absent or route-free). They are reached through application ports from
the request path or the worker, not over HTTP.

## What the old doc claimed that does NOT exist (beyond Kanban)

Called out so the rewrite explicitly removes each, not just the
`/api/*` routes:

1. **`GET /health`** "backward-compatible alias" — no such route.
2. **`HealthRead` schema** (`persistence.backend`,
   `auth.jwt_secret_configured`, `auth.principal_cache_ready`,
   `auth.rate_limiter_backend`, `auth.rate_limiter_ready`,
   `redis.configured`, `redis.ready`) — the real `/health/ready` body
   is `{"status": …, "deps": {…}}`; this schema is fabricated.
3. **`X-API-Key` header / `APP_WRITE_API_KEY` setting** and the entire
   "Protected write endpoints" list — no API-key auth exists anywhere.
4. **`HealthLive` as a named schema** — the real body is a literal
   `{"status":"ok"}`; documenting it as a JSON shape is fine, but not
   as a Kanban-doc-style schema table entry alongside fictional ones.
5. **`https://starter-template-fastapi.dev/problems/board-not-found`**
   `type` value — contradicts the real `urn:problem:*` catalog.
6. The `503` `/health/ready` "degraded" body with a `persistence`/`auth`
   tree — real degraded body is `{"status":"fail","deps":{…}}` with a
   `Retry-After: 1` header.

## What the old doc OMITTED that is real

The document mentions, by accident of the operationId-examples table,
`POST /auth/login`, `POST /auth/logout`, `GET /me`, `PATCH /me`,
`DELETE /me`, `GET /admin/users`, `GET /admin/audit-log`,
`GET /health/live` — but **documents** (with a section) only `GET /`,
`GET /health/live`, `GET /health/ready` (wrongly), and `DELETE /me`.
Every other real endpoint in the inventory above is absent and must be
added: `/auth/register`, `/auth/login`, `/auth/refresh`,
`/auth/logout`, `/auth/logout-all`, `/auth/me`,
`/auth/password/forgot`, `/auth/password/reset`,
`/auth/email/verify/request`, `/auth/email/verify`,
`/admin/audit-log`, `GET /me`, `PATCH /me`, `DELETE /me/erase`,
`GET /me/export`, `GET /admin/users`,
`POST /admin/users/{id}/erase`, `GET /admin/users/{id}/export`.

## Sections kept (already accurate — do NOT rewrite, only re-point examples)

Verified correct against code in this investigation:

- **OpenAPI / operationId convention** — matches
  `src/app_platform/api/operation_ids.py`; the example table rows
  (`auth_login`, `users_get_me`, …) are correct. Keep.
- **Reusable error-response constants** table
  (`AUTH_RESPONSES` 401/403/409/422/429, `USERS_RESPONSES`
  401/403/404/422, `ADMIN_RESPONSES` 400/401/403/404/422) — matches
  `src/app_platform/api/responses.py` exactly. Keep.
- **Problem Details field table** and **Problem-Type URN catalog** —
  matches `ProblemDetails` in `src/app_platform/api/schemas.py` and
  `ProblemType` in `src/app_platform/api/problem_types.py`. Keep.
- **422 `violations` shape + example** — matches `Violation` and the
  production `input`-omission rule. Keep (the example already uses
  `instance: .../me`, a real route — leave it).
- **Keyset-pagination narrative** — matches `admin_list_users`
  (`?cursor=`/`next_cursor`) and `admin_list_audit_events`
  (`?before=`/`next_before`), and the malformed-cursor → `400`
  behavior. Keep.
- **`X-Request-ID` common header** — matches the request-context
  middleware. Keep.
- **`UserPublic` vs `UserPublicSelf`** `authz_version`-redaction
  narrative — matches both schema modules. Keep.

## Decisions / trade-offs

- **Rewrite, not patch.** The fictional content is structurally
  load-bearing (it is the bulk of the doc), so the endpoint/schema/
  error/curl sections are replaced wholesale rather than edited
  line-by-line. The sections proven accurate are preserved verbatim so
  the diff makes the kept-vs-replaced boundary auditable.
- **Document the real auth model once, reference it everywhere.** The
  doc gains a single "Authentication" section describing JWT Bearer +
  the `/auth`-scoped httpOnly refresh cookie; per-endpoint rows just
  say "Bearer" / "refresh cookie" / "none".
- **No file-storage backend prose.** `file_storage` has no HTTP routes;
  the S3-vs-local question is ROADMAP step 7. The doc does not mention
  a storage backend at all — `GET /me/export` / `GET
  /admin/users/{id}/export` are documented by their HTTP contract
  (`ExportResponse` = `download_url` + `expires_at`), not by where the
  blob lives.
- **No new env-var documentation.** The only auth-relevant runtime knob
  surfaced is "access tokens are JWTs, refresh tokens are httpOnly
  cookies"; operational env vars live in `docs/operations.md` (ROADMAP
  step 11), not here.

## Verification gate

Before this change is considered done, the implementer must, for every
endpoint written into `docs/api.md`, produce a grep hit for its
method+path decorator in `src/features/*/adapters/inbound/http/` or
`src/app_platform/api/`. Any endpoint that cannot be grep-verified must
be removed from the doc, not documented speculatively. The same gate
applies to every documented Problem-Type URN (must exist in
`ProblemType`), every documented error `code` (must be produced by
`raise_http_from_auth_error` / `raise_http_from_user_error` / an
`ApplicationHTTPException` call site), and every documented schema field
(must exist on the cited Pydantic model).

## Non-goals

- Editing any doc other than `docs/api.md`.
- Any code, route, schema, error-mapping, settings, middleware,
  migration, or test change.
- Documenting non-HTTP feature surfaces (email/jobs/storage/outbox
  ports, the worker, cron schedules) beyond a one-line "these features
  expose no HTTP routes" statement.
- File-storage backend selection (ROADMAP step 7).
- README / CLAUDE / operations / user-guide / development rewrites
  (ROADMAP steps 9–12).
