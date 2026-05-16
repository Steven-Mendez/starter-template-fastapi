# Tasks

## Phase 1 — Re-derive the real route inventory from code (verification gate)

This phase MUST be completed before any prose is written. The
inventory in `design.md` is the expected result, but the implementer
re-derives it so the doc is anchored to the code as it is *now*, not as
it was during this proposal.

- [x] Grep every inbound HTTP router decorator and record method+path
      for each route:
      - [x] `src/features/authentication/adapters/inbound/http/auth.py`
            (router prefix `/auth`)
      - [x] `src/features/authentication/adapters/inbound/http/admin.py`
            (router prefix `/admin`)
      - [x] `src/features/users/adapters/inbound/http/me.py`
      - [x] `src/features/users/adapters/inbound/http/admin.py`
            (router prefix `/admin`)
      - [x] `src/app_platform/api/root.py` and
            `src/app_platform/api/health.py`
- [x] Confirm there is **no** app-level `/api` prefix: read
      `src/main.py` (`mount_auth_routes` / `mount_users_routes`) and the
      feature wiring modules; the only prefixes are the router-level
      `/auth` and `/admin`.
- [x] Confirm `/api/boards`, `/api/columns`, `/api/cards` have **zero**
      grep hits anywhere under `src/`.
- [x] Confirm there is **no** `GET /health` route (only
      `/health/live` and `/health/ready`).
- [x] Confirm there is **no** `X-API-Key` dependency and **no**
      `APP_WRITE_API_KEY` setting (grep `src/`).
- [x] For each route, record the auth requirement (none / rate-limited
      / `HTTPBearer` via `get_current_principal` or `CurrentPrincipalDep`
      / refresh-cookie+origin / `require_authorization(...)`).
- [x] Audit the real request/response Pydantic models from
      `src/features/authentication/adapters/inbound/http/schemas.py`
      and `src/features/users/adapters/inbound/http/schemas.py`
      (field names, types, required, validation bounds).
- [x] Audit the real `/health/ready` body shapes from
      `src/app_platform/api/health.py` (`{"status":"ok","deps":{…}}`,
      `{"status":"starting"}`, `{"status":"fail","deps":{…}}` +
      `Retry-After: 1`).
- [x] Audit the real error mappings (`code`, HTTP status, `type` URN)
      from
      `src/features/authentication/adapters/inbound/http/errors.py`,
      `src/features/users/adapters/inbound/http/errors.py`, and the
      `ApplicationHTTPException` call sites in `me.py` / `admin.py`.
- [x] Confirm `email`, `background_jobs`, `file_storage`, `outbox`
      expose no inbound HTTP routes.

## Phase 2 — Rewrite `docs/api.md` (the only file edited)

- [x] Fix the **intro / base URL / mounting** section: routers carry
      `/auth` and `/admin` prefixes, mounted at the app root with no
      `/api` prefix; `/`, `/health/live`, `/health/ready` are the
      platform routes; no `/health` alias; email/jobs/storage/outbox
      expose no HTTP routes.
- [x] Replace the **Authentication** section: JWT Bearer access tokens
      (`Authorization: Bearer <token>`, issued by `POST /auth/login` /
      `POST /auth/refresh`) + httpOnly `refresh_token` cookie scoped to
      `/auth`. Delete every `X-API-Key` / `APP_WRITE_API_KEY` /
      "Protected write endpoints" reference.
- [x] Keep the **OpenAPI / operationId** section unchanged (verified
      accurate); confirm the example rows still match
      `src/app_platform/api/operation_ids.py`.
- [x] Keep the **reusable error-response constants** table unchanged
      (verified accurate vs `src/app_platform/api/responses.py`).
- [x] Keep the **Common Response Headers** (`X-Request-ID`) section
      unchanged.
- [x] Keep the **Pagination** narrative; confirm the
      endpoints-that-paginate table still names `GET /admin/users`
      (`?cursor=`) and `GET /admin/audit-log` (`?before=`).
- [x] Keep the **Problem Details field table** and **Problem-Type URN
      catalog** unchanged (verified vs `ProblemDetails` / `ProblemType`).
- [x] Keep the **422 `violations`** shape + example unchanged.
- [x] Replace the **"Example application error"** block: swap the
      `board-not-found` body for a real one drawn from an actual
      mapping (e.g. `urn:problem:auth:invalid-credentials` `401` on
      wrong-password `POST /auth/login`, or
      `urn:problem:authz:permission-denied` `403` on non-admin
      `GET /admin/users`).
- [x] Rewrite the **Status Codes** table in terms of real endpoints:
      remove Kanban rows ("Board… created", "Card move violated…") and
      the `X-API-Key` `401` row; cover `200/201/202/204/400/401/403/
      404/409/422/429/500/503` against the real surface.
- [x] Delete the fictional **Schemas** section
      (`BoardCreate`/`BoardUpdate`/`BoardSummary`/`BoardDetail`/
      `ColumnCreate`/`ColumnRead`/`CardCreate`/`CardUpdate`/`CardRead`/
      `HealthRead`) and document the real schemas from Phase 1
      (`RegisterRequest`, `LoginRequest`, `PasswordForgotRequest`,
      `PasswordResetRequest`, `EmailVerifyRequest`, `UserPublic`,
      `UserPublicSelf`, `PrincipalPublic`, `TokenResponse`,
      `MessageResponse`, `InternalTokenResponse`, `AuditEventRead`,
      `AuditLogRead`, `UpdateProfileRequest`, `UserListPage`,
      `EraseSelfRequest`, `ErasureAccepted`, `ExportResponse`). Keep the
      already-correct `UserPublic`-vs-`UserPublicSelf` redaction
      narrative.
- [x] Replace the **Endpoints** section with the full real inventory
      from Phase 1: `GET /`, `GET /health/live`, `GET /health/ready`
      (real `deps` body + `starting`/`fail`+`Retry-After` variants),
      all `/auth/*`, `GET /admin/audit-log`, `GET/PATCH/DELETE /me`,
      `DELETE /me/erase`, `GET /me/export`, `GET /admin/users`,
      `POST /admin/users/{user_id}/erase`,
      `GET /admin/users/{user_id}/export`. Delete every `/api/boards`,
      `/api/columns`, `/api/cards` endpoint section.
- [x] Replace the **Curl Examples** with a real flow (e.g. register →
      login → call a Bearer-protected endpoint); delete the
      `POST /api/boards` / `X-API-Key` examples.
- [x] Final grep sweep of the rewritten `docs/api.md`: zero occurrences
      of `board`, `column`, `card` (Kanban sense), `/api/boards`,
      `/api/columns`, `/api/cards`, `X-API-Key`, `APP_WRITE_API_KEY`,
      `GET /health` (alias), `HealthRead`, or
      `starter-template-fastapi.dev/problems`.

## Phase 3 — Verification gate (must pass before done)

- [x] Every endpoint written into `docs/api.md` has a grep hit for its
      method+path decorator in `src/features/*/adapters/inbound/http/`
      or `src/app_platform/api/`. Any non-greppable endpoint is removed,
      not documented speculatively.
- [x] Every documented Problem-Type URN exists in `ProblemType`
      (`src/app_platform/api/problem_types.py`).
- [x] Every documented error `code` is produced by
      `raise_http_from_auth_error` / `raise_http_from_user_error` / an
      `ApplicationHTTPException` call site.
- [x] Every documented schema field exists on the cited Pydantic model.
- [x] No file other than `docs/api.md` and the OpenSpec change
      artifacts has been modified (`git status` confirms).
- [x] No `src/` file, migration, or test changed.

## Phase 4 — Spec + archive

- [x] `openspec validate fix-api-docs-kanban --strict` passes (the
      `## MODIFIED Requirements` delta on `project-layout` satisfies the
      ≥1-delta-op rule; the requirement name byte-matches the canonical
      header).
- [ ] Flip ROADMAP `ETAPA I` step 8 checkbox to `[x]` as part of the
      archive step (not in this change's content).
- [ ] Archive WITHOUT `--skip-specs`
      (`openspec archive fix-api-docs-kanban`) so the added scenario
      folds into `openspec/specs/project-layout/spec.md`.
