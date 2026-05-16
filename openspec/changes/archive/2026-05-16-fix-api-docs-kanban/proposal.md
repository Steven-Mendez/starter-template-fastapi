## Why

ROADMAP ETAPA I step 8 ("dejar el repo honesto"): rewrite `docs/api.md`
so it documents the HTTP surface the code actually exposes and removes
every reference to the fictional Kanban API (`/api/boards`,
`/api/columns`, `/api/cards`). The ROADMAP line is explicit: *"borrar
todas las referencias a endpoints Kanban … No existen en el código."*

`docs/api.md` is 714 lines and is, end-to-end, a description of a Kanban
service that **does not exist anywhere in the source tree**. A
line-by-line audit against the code found that the document is wrong in
four independent ways, not one:

1. **Fictional resource API.** `POST/GET /api/boards`,
   `GET/PATCH/DELETE /api/boards/{id}`,
   `POST /api/boards/{id}/columns`, `DELETE /api/columns/{id}`,
   `POST /api/columns/{id}/cards`, `GET/PATCH /api/cards/{id}` — none of
   these routes exist. A repo-wide grep of every inbound HTTP router
   (`src/features/*/adapters/inbound/http/`, `src/app_platform/api/`)
   returns zero `/api/boards`, `/api/columns`, or `/api/cards`
   registrations. The `BoardCreate` / `BoardUpdate` / `BoardSummary` /
   `BoardDetail` / `ColumnCreate` / `ColumnRead` / `CardCreate` /
   `CardUpdate` / `CardRead` schemas describe Pydantic models that do
   not exist. The `board-not-found` / `column_not_found` /
   `card_not_found` / `invalid_card_move` / `patch_no_changes` error
   codes are not produced anywhere. The `https://starter-template-fastapi.dev/problems/board-not-found`
   `type` URI contradicts the service's real, code-defined
   `urn:problem:<domain>:<code>` catalog (`ProblemType` in
   `src/app_platform/api/problem_types.py`).

2. **Fictional authentication model.** The doc says write endpoints are
   gated by an `X-API-Key` header configured via `APP_WRITE_API_KEY`.
   No such mechanism exists. There is no `APP_WRITE_API_KEY` setting,
   no `X-API-Key` dependency, and no API-key middleware. The real auth
   model is JWT Bearer access tokens (issued by `POST /auth/login` /
   `/auth/refresh`, sent as `Authorization: Bearer <token>`,
   resolved via `HTTPBearer` in `src/app_platform/api/authorization.py`)
   plus an `httpOnly` refresh-token cookie scoped to `/auth`.

3. **Fictional health surface.** The doc documents a `GET /health`
   "backward-compatible alias" and a `HealthRead` schema with
   `persistence.backend`, `auth.jwt_secret_configured`,
   `auth.rate_limiter_backend`, etc. The code has **no** `GET /health`
   route (only `GET /health/live` and `GET /health/ready` are
   registered in `src/app_platform/api/root.py` /
   `src/app_platform/api/health.py`). The real `/health/ready` body is
   `{"status": "ok"|"starting"|"fail", "deps": {<name>: "ok" | {"status":"fail","reason":"…"}}}`,
   not the documented `persistence`/`auth` tree.

4. **Every real endpoint is omitted.** The document does not mention a
   single one of the ~25 routes the service actually serves: the
   `/auth/*` surface (register, login, logout, logout-all, refresh,
   `/auth/me`, password forgot/reset, email verify request/confirm),
   the admin audit log, the users `/me` surface (`GET`/`PATCH`/`DELETE`,
   GDPR erase/export), and the admin users surface (list, erase,
   export). The only two real things in the entire doc — `GET /`,
   `GET /health/live`, and most of the Problem Details / pagination /
   operationId narrative — happen to be correct because they describe
   platform behavior, not the (nonexistent) Kanban feature.

This step rewrites `docs/api.md` against the code: every documented
endpoint, payload, status, and error must be greppable in the inbound
HTTP layer. The good structural bones of the document (intro,
OpenAPI/operationId section, reusable error-response constants,
Problem Details + URN catalog, pagination, status codes, schemas,
curl examples) are kept — they are accurate platform behavior — and
re-pointed at the real surface. The fictional Kanban content is
deleted, not relocated.

### Scope boundary (other ROADMAP steps own the other docs)

Only `docs/api.md` is rewritten here. `README.md`,
`CLAUDE.md`, `docs/operations.md`, `docs/user-guide.md`, and
`docs/development.md` also carry Kanban or removed-backend references,
but those files are owned by ROADMAP steps 9 (README AWS-first
tagline), 10 (CLAUDE.md re-framing), 11 (`docs/operations.md` trim),
and 12 (`src/cli/` docs) — or are simply out of this step's scope.
Touching them here would collide with those steps. This change MUST
NOT edit any doc other than `docs/api.md`.

### No code, route, or test changes

This is a documentation-accuracy change. No route is added, removed, or
renamed. No Pydantic schema, error mapping, settings field, or test is
touched. No migration. The HTTP surface the doc will describe already
exists and is unchanged; only the prose catches up to it.

The `email`, `background_jobs`, `file_storage`, and `outbox` features
have **no inbound HTTP routes** (they are port-driven and run in the
worker / request path via ports, not via routers). The rewritten doc
states this explicitly rather than inventing endpoints for them. In
particular, the rewrite makes **no** file-storage backend claim — the
S3-adapter status is being resolved separately in ROADMAP step 7, and
`file_storage` has no inbound HTTP routes, so the question does not
arise in this document; no file-storage backend prose is added.

## What Changes

- Rewrite `docs/api.md` to document the real HTTP surface, derived from
  the inbound routers, with every endpoint verifiable by grep:

  **Public auth (`features/authentication`, router prefix `/auth`,
  `src/features/authentication/adapters/inbound/http/auth.py`):**
  - `POST /auth/register` — `RegisterRequest` → `UserPublic`, `201`
  - `POST /auth/login` — `LoginRequest` → `TokenResponse` (+ sets the
    `refresh_token` httpOnly cookie scoped to `/auth`)
  - `POST /auth/refresh` — refresh cookie → `TokenResponse`, origin-checked
  - `POST /auth/logout` — refresh cookie → `MessageResponse`,
    clears the cookie
  - `POST /auth/logout-all` — Bearer → `MessageResponse`, clears the cookie
  - `GET /auth/me` — Bearer → `PrincipalPublic`
  - `POST /auth/password/forgot` — `PasswordForgotRequest` →
    `InternalTokenResponse`, `202`
  - `POST /auth/password/reset` — `PasswordResetRequest` →
    `MessageResponse`
  - `POST /auth/email/verify/request` — Bearer → `InternalTokenResponse`,
    `202`
  - `POST /auth/email/verify` — `EmailVerifyRequest` → `MessageResponse`

  **Admin auth (router prefix `/admin`,
  `src/features/authentication/adapters/inbound/http/admin.py`):**
  - `GET /admin/audit-log` — Bearer + `require_authorization("read_audit",
    "system", None)` → `AuditLogRead`, keyset-paginated via `?before=`

  **Users self (`features/users`,
  `src/features/users/adapters/inbound/http/me.py`):**
  - `GET /me` — Bearer → `UserPublicSelf`
  - `PATCH /me` — Bearer + `UpdateProfileRequest` → `UserPublicSelf`
  - `DELETE /me` — Bearer → `204` (revokes refresh-token families,
    clears the cookie)
  - `DELETE /me/erase` — Bearer + `EraseSelfRequest` (password re-auth)
    → `ErasureAccepted`, `202`, `Location` header (GDPR Art. 17)
  - `GET /me/export` — Bearer → `ExportResponse` (GDPR Art. 15)

  **Users admin (router prefix `/admin`,
  `src/features/users/adapters/inbound/http/admin.py`):**
  - `GET /admin/users` — Bearer + `require_authorization("manage_users",
    "system", None)` → `UserListPage`, keyset-paginated via `?cursor=`
  - `POST /admin/users/{user_id}/erase` — Bearer + `manage_users` →
    `ErasureAccepted`, `202`, `Location` header
  - `GET /admin/users/{user_id}/export` — Bearer + `manage_users` →
    `ExportResponse`

  **Platform (`src/app_platform/api/root.py`,
  `src/app_platform/api/health.py`):**
  - `GET /` — static `{"name","message"}` heartbeat
  - `GET /health/live` — `{"status":"ok"}`, process-only liveness
  - `GET /health/ready` — readiness probe; `200` `{"status":"ok","deps":{…}}`,
    `503` `{"status":"starting"}` during boot, `503`
    `{"status":"fail","deps":{…}}` + `Retry-After: 1` on a failed probe

- Replace the fictional **authentication** section: document the JWT
  Bearer access-token model and the httpOnly refresh-token cookie
  scoped to `/auth` (issued by `POST /auth/login` and `POST
  /auth/refresh`, read by `/auth/refresh` and `/auth/logout`).
  Delete every `X-API-Key` / `APP_WRITE_API_KEY` reference and the
  "Protected write endpoints" list — that mechanism does not exist.

- Replace the fictional **error examples**: the
  `https://starter-template-fastapi.dev/problems/board-not-found`
  example becomes a real Problem Details body drawn from an actual
  mapping in
  `src/features/authentication/adapters/inbound/http/errors.py`
  (e.g. `urn:problem:auth:invalid-credentials` `401` on a wrong-password
  `POST /auth/login`, or `urn:problem:authz:permission-denied` `403` on
  a non-admin `GET /admin/users`). Keep the existing, correct
  Problem-Type URN catalog table (it already matches `ProblemType`) and
  the 422 `violations` example (already correct).

- Replace the fictional **schema** section: delete the
  `BoardCreate`/`BoardUpdate`/`BoardSummary`/`BoardDetail`/`ColumnCreate`/
  `ColumnRead`/`CardCreate`/`CardUpdate`/`CardRead`/`HealthRead` tables
  and document the real request/response models audited from
  `src/features/authentication/adapters/inbound/http/schemas.py` and
  `src/features/users/adapters/inbound/http/schemas.py`:
  `RegisterRequest`, `LoginRequest`, `PasswordForgotRequest`,
  `PasswordResetRequest`, `EmailVerifyRequest`, `UserPublic` (auth +
  users variants), `UserPublicSelf`, `PrincipalPublic`, `TokenResponse`,
  `MessageResponse`, `InternalTokenResponse`, `AuditEventRead`,
  `AuditLogRead`, `UpdateProfileRequest`, `UserListPage`,
  `EraseSelfRequest`, `ErasureAccepted`, `ExportResponse`. The
  `UserPublic`-vs-`UserPublicSelf` distinction (the `authz_version`
  redaction) and the keyset-pagination narrative are already correct and
  are kept.

- Fix the **status-code** table: remove the Kanban-specific rows
  ("Board, column, or card created", "Card move violated a domain
  rule", etc.) and the `X-API-Key` `401` row; describe the real status
  codes (`200`/`201`/`202`/`204`/`400`/`401`/`403`/`404`/`409`/`422`/
  `429`/`500`/`503`) in terms of the real endpoints and error mappings.

- Fix the **base URL / mounting** section: the routers carry their own
  prefixes (`/auth`, `/admin`) and are mounted at the app root with no
  extra `/api` prefix (`app.include_router(build_auth_router())` etc. in
  `src/main.py` / the feature wiring). State that `/health/live` and
  `/health/ready` are the only health routes (no `/health` alias) and
  that `email`/`background_jobs`/`file_storage`/`outbox` expose no HTTP
  routes.

- Replace the **curl examples**: the `POST /api/boards` examples become
  real flows against existing routes (e.g. register → login → call a
  Bearer-protected endpoint).

- Keep, unchanged, the already-correct sections: OpenAPI /
  `operationId` convention, the reusable error-response constants table
  (`AUTH_RESPONSES`/`USERS_RESPONSES`/`ADMIN_RESPONSES`), the Problem
  Details field table, the Problem-Type URN catalog, the 422
  `violations` shape and example, the keyset-pagination narrative, and
  the `X-Request-ID` common-header note — all verified against
  `src/app_platform/api/responses.py`,
  `src/app_platform/api/problem_types.py`, and
  `src/app_platform/api/schemas.py`.

**Capabilities — Modified**
- `project-layout`: the existing "Documentation reflects the new
  layout" requirement is re-stated verbatim and gains one scenario
  asserting that `docs/api.md` documents only HTTP routes that exist in
  the inbound layer and contains no Kanban (`/api/boards`,
  `/api/columns`, `/api/cards`) reference. This is the same requirement
  the directly-analogous prior doc-cleanup change
  (`remove-template-scaffold-docs`, archived 2026-05-16) refined, and it
  already governs the content of `docs/*.md`. The strict validator
  requires every change to carry ≥1 delta op; a docs-accuracy refinement
  of this requirement is the honest delta target (a zero-delta
  `--skip-specs` archive would fail `openspec validate --strict`, exactly
  as called out in the `remove-template-scaffold-docs` SPEC-DELTA note).

**Capabilities — New**
- None.

<!-- SPEC-DELTA DECISION (for the orchestrator):

     There is no api-doc-specific requirement and no requirement that
     mentions Kanban (grep of openspec/specs/**/spec.md: the only hits
     for "/api/boards" / "Kanban" are in project-layout's prose example
     and authorization's prose, not in a requirement that this change
     alters). The applicable existing requirement is
     `project-layout` → "Documentation reflects the new layout"
     (specs/project-layout/spec.md line 93), which already governs the
     content of `CLAUDE.md`, `README.md`, and `docs/*.md`. Asserting
     that `docs/api.md` documents only real routes is a genuine
     refinement of that requirement, so this change ships a
     `## MODIFIED Requirements` delta that re-states it verbatim plus
     one ADDED scenario. The requirement name in the delta byte-matches
     the canonical header. Archive WITHOUT `--skip-specs`
     (`openspec archive fix-api-docs-kanban`) so the new scenario folds
     into the canonical project-layout spec. -->

## Impact

- **Docs**: `docs/api.md` only — rewritten so every documented
  endpoint, payload, status, header, and error code is greppable in
  `src/features/*/adapters/inbound/http/` or `src/app_platform/api/`.
  No other doc is touched (README/CLAUDE/operations/user-guide/
  development are ROADMAP steps 9–12 or out of scope).
- **Code**: none. No router, schema, error mapping, dependency,
  settings field, or middleware is changed. The HTTP surface the doc
  describes already exists exactly as written.
- **Migrations**: none.
- **Settings / env / production validator**: none. No env var is added,
  removed, or documented as required; in particular no
  `APP_WRITE_API_KEY` (it never existed) and no file-storage backend
  prose (ROADMAP step 7 territory; `file_storage` has no HTTP routes).
- **Tests**: none deleted or edited. The OpenAPI presence test
  (`src/features/authentication/tests/e2e/test_openapi_problem_details.py`)
  already pins the real operationId/Problem-Details contract; this
  change documents what that test already enforces and adds nothing it
  must satisfy.
- **Spec delta**: one `## MODIFIED Requirements` delta on the
  `project-layout` capability (`specs/project-layout/spec.md`) — the
  "Documentation reflects the new layout" requirement re-stated verbatim
  with one ADDED scenario about `docs/api.md` route-accuracy. No
  requirement is removed; no behavior outside documentation content
  changes. Archive WITHOUT `--skip-specs`.
- **Production behavior**: unchanged. Documentation only.
- **Backwards compatibility**: any reader who tried to call
  `/api/boards` or send `X-API-Key` was already calling a 404 / a
  no-op header; the doc now describes the routes that actually respond.

## Out of scope (do NOT touch)

- `README.md` — ROADMAP step 9 (AWS-first tagline + feature matrix).
  It still carries Kanban / removed-backend references; leave them.
- `CLAUDE.md` — ROADMAP step 10 (feature-matrix re-framing,
  production-rule trim).
- `docs/operations.md` — ROADMAP step 11 (production "refuses to
  start if…" trim).
- `docs/user-guide.md`, `docs/development.md`, and any other
  `docs/*.md` that carry Kanban references — not part of step 8's
  brief; a later step / change owns them. Reviewers should reject any
  edit in this change that touches a file other than `docs/api.md`
  (and the OpenSpec change artifacts).
- Any code, route, schema, error mapping, dependency, settings field,
  middleware, migration, or test — this is a documentation-accuracy
  change only.
- The S3 / file-storage backend question — ROADMAP step 7.
  `file_storage` has no inbound HTTP routes, so `docs/api.md` makes no
  file-storage backend claim at all; do not add one.
- Amazon / AWS endpoints or config — not introduced by this step.

This change is strictly ROADMAP ETAPA I step 8. It does not advance
steps 7 or 9–12, adds no AWS code, and changes no runtime behavior.
