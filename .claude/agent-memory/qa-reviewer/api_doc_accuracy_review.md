---
name: api-doc-accuracy-review
description: Recipe for QA-ing docs/api.md rewrites against the real inbound HTTP layer (ROADMAP ETAPA I step 8 fix-api-docs-kanban and successors)
metadata:
  type: project
---

`docs/api.md` was historically a wholly-fictional Kanban API doc. ROADMAP
ETAPA I step 8 (`fix-api-docs-kanban`) rewrote it against code. When QA-ing
this or any successor api-doc change:

**Why:** the defect class this step exists to eliminate is "documented
endpoint/field/status that does not exist in code". Verify everything
against source, not against the proposal's inventory.

**How to apply — the authoritative route inventory (22 routes as of
2026-05-16):** grep `@<router>.<verb>(` across
`src/features/authentication/adapters/inbound/http/{auth,admin}.py`,
`src/features/users/adapters/inbound/http/{me,admin}.py`,
`src/app_platform/api/{root,health}.py`. Router prefixes: auth
`auth_router` `/auth`, auth `admin_router` `/admin`, users `me_router`
(no prefix), users `admin_router` `/admin`, platform `root_router`
(no prefix; `health_router` is `include_router`-ed into it). No app-level
`/api` prefix.

- `health_live`/`read_root`/`health_ready` are all declared on/under
  `root_router` (`tags=["root"]`), so their operationIds are
  `root_health_live` / `root_read_root` / `root_health_ready` — verify
  empirically with `PYTHONPATH=src uv run python -c "...app.openapi()..."`.
  NOTE: `src/app_platform/api/operation_ids.py` docstring example still
  says `GET /health/live → health_liveness` — that example is STALE but
  is source code outside a docs-only change's scope; not a doc defect.
- Auth `UserPublic` HAS `last_login_at: datetime | None`; users
  `UserPublic` does NOT. `UserPublicSelf` redacts exactly
  `{"authz_version"}` vs users `UserPublic`. A unit test pins this
  symmetric difference.
- `POST /auth/password/forgot` and `/auth/email/verify/request` and
  `/auth/password/reset`-sibling decorators carry explicit
  `status_code=202`; login/refresh/logout default to 200.
- ProblemType URN catalog: 9 URNs + `about:blank` in
  `src/app_platform/api/problem_types.py`. Error `code` strings live in
  `errors.py` mappers (auth/users) + `ApplicationHTTPException` call
  sites in users `me.py`/`admin.py` (`erasure_pipeline_unwired`,
  `export_pipeline_unwired`, `invalid_credentials`, `invalid_cursor`).
  The catalog table is URN-level; a `StaleTokenError`→`code=stale_token`
  but `type=urn:problem:auth:token-stale` mismatch between code-slug and
  URN-slug is EXPECTED, not a defect.
- `email`/`background_jobs`/`file_storage`/`outbox`: `email` has an
  empty `adapters/inbound/__init__.py` (no router); the other three have
  no `adapters/inbound` dir at all. Doc's "no inbound HTTP routes"
  statement is accurate.
- Response constants in `src/app_platform/api/responses.py`:
  `AUTH_RESPONSES` 401/403/409/422/429, `USERS_RESPONSES`
  401/403/404/422, `ADMIN_RESPONSES` 400/401/403/404/422.

**Scope:** only `docs/api.md` may change (+ openspec change dir). An
untracked `openspec/changes/remove-s3-stub/` is a SEPARATE change
(ROADMAP step 7) — not in scope, do not flag. `make quality` passing
(22 import contracts + mypy 479 files) is the proof no `src/` was
touched on a docs-only change.
