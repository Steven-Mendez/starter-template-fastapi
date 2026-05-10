## Why

The template currently demonstrates flat RBAC: users hold roles, roles grant permissions, and routes are gated globally with `require_permissions("kanban:read")`. That teaches the simplest possible authorization model, but it leaves the hardest part of real-world backends — *who can act on **this** resource?* — unmodeled. Audit fields (`created_by`, `updated_by`) are populated on every kanban row but never consulted; route guards are global, not resource-scoped.

A starter template that ships with ReBAC instead of RBAC is far more valuable: it teaches relationship-based authorization (the model behind Google Zanzibar, SpiceDB, OpenFGA, AWS Cedar) end-to-end, with a clean port that lets readers swap the in-repo engine for a production system without rewriting the application layer. Greenfield removal of RBAC keeps the template pure — no two-pattern confusion, no deprecation paths to maintain.

## What Changes

- **BREAKING** Remove RBAC entirely: drop `roles`, `permissions`, `role_permissions`, `user_roles` tables; delete RBAC use cases, ports, admin routes, JWT `roles` claim, and seeded role/permission grid.
- **BREAKING** Remove `require_permissions` / `require_any_permission` FastAPI dependencies and the `roles`/`permissions` fields on `Principal`.
- Introduce an `AuthorizationPort` (Zanzibar-flavored API: `check`, `lookup_resources`, `lookup_subjects`, `write_relationships`, `delete_relationships`) and ship two adapters: an in-repo SQLModel engine as the default and a non-functional SpiceDB stub demonstrating that the port is the swap boundary.
- Add a `relationships` table modeled on Zanzibar tuples: `(resource_type, resource_id, relation, subject_type, subject_id)` with appropriate indexes and a uniqueness constraint.
- Introduce a `require_authorization(action, resource_type, id_loader)` FastAPI dependency that loads the resource id from the path, dispatches through an `(resource_type, action) → required relations` map, and raises 403 on deny.
- Define the kanban relation hierarchy: `owner ⊇ writer ⊇ reader` on board, with computed cross-resource inheritance so cards and columns inherit relations from their parent board at check time. No per-card or per-column tuples are stored.
- Define a `system` resource with a single `admin` relation. Bootstrap rewrites to write `system:main#admin@user:{id}` instead of assigning a `super_admin` role.
- Move kanban authorization onto resource-scoped checks: `POST /boards` writes the initial owner tuple from the actor; `GET /boards` lists only the resources the user has reader+ on; `GET/PATCH/DELETE /boards/{id}` and all column/card endpoints check via the parent-board chain.
- Surviving auth admin endpoints (`GET /admin/users`, `GET /admin/audit-log`) check on `system:main`. Role/permission management endpoints are deleted (no concept exists in the new model).
- Keep `User.authz_version` and the principal-cache invalidation contract — bumped on any relationship write affecting the user, so JWTs reflect authz changes within the cache TTL.
- Single Alembic migration: drops the four RBAC tables and adds `relationships`. Tests for RBAC use cases are deleted; new unit, integration, and e2e tests cover the engine, port, hierarchy, and cross-resource inheritance.

## Capabilities

### New Capabilities

- `authorization`: Relationship-based access control for the template. Defines the AuthorizationPort, relationship semantics, hierarchy and cross-resource inheritance rules, the action-to-relation dispatch contract, the bootstrap relationship-seeding behavior, and the cache-invalidation contract via `User.authz_version`. Owns how kanban and system-admin endpoints are authorized.

### Modified Capabilities

<!-- No prior capability specs exist in openspec/specs/. RBAC behavior was implicit in code; this change replaces it with the new `authorization` capability above. -->

## Impact

- **Database**: drops `roles`, `permissions`, `role_permissions`, `user_roles`; adds `relationships`. One Alembic migration; downgrade restores empty RBAC tables (data is not preserved — this is a template).
- **Auth feature**:
  - Deletes ~13 RBAC use cases under `application/use_cases/rbac/` (only `bootstrap_super_admin`, `list_users`, `list_audit_events` survive in modified form).
  - Deletes RBAC ports, `application/seed.py`, `Role`/`Permission` domain models and tables.
  - Rewrites `bootstrap_super_admin` to write the system-admin tuple and bump `authz_version`.
  - Updates `AccessTokenService` to drop the `roles` claim from issue and decode.
  - Updates `Principal` to drop `roles` and `permissions`.
  - Removes RBAC admin HTTP routes; keeps `/admin/users` and `/admin/audit-log` behind the new `system.manage_users` / `system.read_audit` actions.
- **Kanban feature**:
  - `main.py` route mounting: replaces `require_permissions("kanban:read"/"kanban:write")` with the new `require_authorization` dependency wired per route.
  - `CreateBoardUseCase` writes the initial `kanban:{board.id}#owner@user:{actor_id}` tuple after the board is persisted.
  - `ListBoardsUseCase` consults `lookup_resources` to filter at the authz layer.
  - All read/write/delete board, column, and card flows route through `AuthorizationPort.check`.
- **Platform**:
  - `platform/api/authorization.py` rewritten: removes `require_permissions`, adds `require_authorization`.
  - Adds `application/authorization/` (ports, actions map, errors).
  - Adds `adapters/outbound/authorization/sqlmodel/` (default in-repo engine + repository).
  - Adds `adapters/outbound/authorization/spicedb/` stub (non-functional, `# pragma: no cover`).
- **Tests**: 4 RBAC test files deleted; new unit/integration/e2e suites for the engine, port, hierarchy, computed inheritance, listing, and bootstrap.
- **Docs / configuration**: CLAUDE.md and `.env.example` updates land in the follow-up `template-quality-cleanups` proposal; no doc changes in this change beyond what's strictly needed by the new code.
- **Out of scope (deferred to follow-up)**: CLAUDE.md rewrite, `RateLimiterPort`, auth/kanban repository pattern alignment, `RequestContext` dependency, settings-driven rate-limit thresholds, Specification framework decision, three-Redis-clients consolidation, move-card HTTP test gap.
