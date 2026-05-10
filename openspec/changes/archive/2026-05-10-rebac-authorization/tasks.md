## 1. Application-layer authorization scaffolding

- [x] 1.1 Create `src/features/auth/application/authorization/` package with empty `__init__.py`
- [x] 1.2 Add `application/authorization/errors.py` defining `NotAuthorizedError(AuthError)`
- [x] 1.3 Add `application/authorization/ports.py` with `AuthorizationPort` Protocol exposing `check`, `lookup_resources` (with `limit` parameter, default 100, max 500), `lookup_subjects`, `write_relationships`, `delete_relationships`
- [x] 1.4 Add `application/authorization/actions.py` with `ACTIONS` map per the spec (kanban: read/update/delete; system: manage_users/read_audit) and a helper `relations_for(resource_type, action) -> frozenset[str]` that raises a clear error on unknown pairs
- [x] 1.5 Add `application/authorization/hierarchy.py` exposing `expand_relations(resource_type, relations) -> frozenset[str]` so a check for `reader` includes `{reader, writer, owner}` for kanban
- [x] 1.6 Add `application/authorization/resource_graph.py` exposing a `ParentResolver` Protocol and a default in-process implementation that walks `card → column → board` via `KanbanLookupRepositoryPort`
- [x] 1.7 Define a `Relationship` value object (frozen dataclass with `resource_type`, `resource_id`, `relation`, `subject_type`, `subject_id`) under `application/authorization/types.py` (or co-locate in `ports.py` if smaller)

## 2. Database schema and SQLModel adapter

- [x] 2.1 Add `RelationshipTable` SQLModel under `src/features/auth/adapters/outbound/persistence/sqlmodel/models.py` (or new module) with the columns and constraints from the spec
- [x] 2.2 Add a unique constraint on `(resource_type, resource_id, relation, subject_type, subject_id)` and the two indexes from the spec
- [x] 2.3 Generate Alembic migration: `uv run alembic revision --autogenerate -m "rebac: drop rbac, add relationships"`; hand-edit to drop `roles`, `permissions`, `role_permissions`, `user_roles` and create `relationships`
- [x] 2.4 Implement migration `downgrade()` to recreate empty RBAC tables and drop `relationships` so round-trip tests pass
- [x] 2.5 Create `src/features/auth/adapters/outbound/authorization/__init__.py`, `sqlmodel/__init__.py`, and `sqlmodel/repository.py`
- [x] 2.6 Implement `SQLModelAuthorizationAdapter(AuthorizationPort)` in `repository.py`:
  - `check`: dispatch on resource_type; for kanban, expand the action's relation set via hierarchy and (for card/column) walk to the parent board via `ParentResolver`
  - `lookup_resources`: query relationships filtered by `(subject, resource_type, relation IN expanded)`, return distinct ids, apply pagination
  - `lookup_subjects`: query relationships filtered by `(resource_type, resource_id, relation IN expanded)`, return distinct subject ids
  - `write_relationships` / `delete_relationships`: bulk write/delete; deduplicate on conflict; on each call, collect the set of affected user subjects and invoke `repository.increment_user_authz_version(user_id)` for each, in the same session
- [x] 2.7 Add a module docstring to `repository.py` documenting the check-time resolution strategy and naming the scaling cliff (per design doc D3)

## 3. SpiceDB stub adapter

- [x] 3.1 Create `src/features/auth/adapters/outbound/authorization/spicedb/__init__.py` and `spicedb/adapter.py`
- [x] 3.2 Implement `SpiceDBAuthorizationAdapter(AuthorizationPort)` with each method raising `NotImplementedError("SpiceDB integration is a stub; see README.md")`; mark the class body and methods with `# pragma: no cover`
- [x] 3.3 Write `spicedb/README.md` documenting the SpiceDB API → port method mapping and including a runnable `.zed` schema for the `kanban` and `system` resource types

## 4. Platform-side `require_authorization` dependency

- [x] 4.1 Open `src/platform/api/authorization.py`; remove `require_permissions` and `require_any_permission` (and any helpers they used)
- [x] 4.2 Add `require_authorization(action: str, resource_type: str, id_loader: Callable[[Request], str] | None = None)` returning a FastAPI dependency
- [x] 4.3 Resolve the current principal via the existing principal resolver; resolve resource id via `id_loader(request)` or use sentinel `"main"` when `id_loader` is None
- [x] 4.4 Call `auth.check(...)`; on deny, raise `HTTPException(403, "Permission denied")`; on missing principal, raise the existing 401
- [x] 4.5 Update `src/platform/api/__init__.py` exports
- [x] 4.6 Add unit tests under `src/platform/tests/test_authorization_dependency.py` covering: deny → 403, allow → next dependency runs, no `id_loader` → uses `"main"`

## 5. Auth domain and persistence: drop Role/Permission, keep User.authz_version

- [x] 5.1 Delete `Role`, `Permission` dataclasses from `src/features/auth/domain/models.py`
- [x] 5.2 Delete `RoleTable`, `PermissionTable`, `RolePermissionTable`, `UserRoleTable` from `adapters/outbound/persistence/sqlmodel/models.py`
- [x] 5.3 Remove the corresponding mappers (`_to_role`, `_to_permission`) and all role/permission/role-permission/user-role methods from `SQLModelAuthRepository`
- [x] 5.4 Remove `_get_principal_from_session` joins on `RoleTable`/`PermissionTable`/`RolePermissionTable`/`UserRoleTable`; rewrite to return a `Principal` with no `roles`/`permissions` (only `user_id`, `email`, `is_active`, `is_verified`, `authz_version`)
- [x] 5.5 Remove `increment_authz_for_role_users` and `list_user_ids_for_role` from the repository
- [x] 5.6 Update `Principal` in `src/platform/shared/principal.py` to drop `roles` and `permissions` fields
- [x] 5.7 Update `AuthRepositoryPort` in `application/ports/outbound/auth_repository.py` to drop role/permission methods

## 6. Drop RBAC use cases and ports

- [x] 6.1 Delete `src/features/auth/application/use_cases/rbac/assign_role_permission.py`
- [x] 6.2 Delete `assign_user_role.py`, `create_permission.py`, `create_role.py`, `list_permissions.py`, `list_roles.py`, `remove_role_permission.py`, `remove_user_role.py`, `seed_initial_data.py`, `update_role.py`
- [x] 6.3 Delete `src/features/auth/application/seed.py` (the ALL_PERMISSIONS / ROLE_PERMISSIONS / ROLE_DESCRIPTIONS constants)
- [x] 6.4 Delete `src/features/auth/application/ports/inbound/rbac_ports.py`
- [x] 6.5 Keep `list_users.py` and `list_audit_events.py` unchanged (they're not RBAC, only mounted under /admin)
- [x] 6.6 Update `application/use_cases/rbac/__init__.py` exports — or delete the package entirely if only `list_audit_events`/`list_users` survive (move them under `application/use_cases/admin/` instead, since they're no longer RBAC)

## 7. Rewrite `BootstrapSuperAdmin` to write the system tuple

- [x] 7.1 Move `bootstrap_super_admin.py` to a new home (`application/use_cases/admin/bootstrap_admin.py`) and rename the class to `BootstrapSystemAdmin`
- [x] 7.2 Remove dependency on `SeedInitialData`; require `AuthorizationPort` instead
- [x] 7.3 Implement the flow: register-or-lookup user → `auth.write_relationships([Relationship("system", "main", "admin", "user", str(user.id))])` → record audit `authz.bootstrap_admin_assigned`
- [x] 7.4 Update `src/main.py:_run_auth_bootstrap` to call the renamed use case; drop the `seed_initial_data.execute()` call
- [x] 7.5 Update `src/features/auth/management.py` (CLI) to call the renamed use case; remove the `seed` subcommand
- [x] 7.6 Verify the env var pair check still raises `RuntimeError` with both-or-neither rule (preserved in main.py logic; will verify after phase 10)

## 8. JWT token claim removal

- [x] 8.1 Update `application/jwt_tokens.py:AccessTokenService.issue` signature to drop `roles`; remove the `roles` payload key; update docstring
- [x] 8.2 Update `application/jwt_tokens.py:AccessTokenService.decode` to no longer require or read `roles`; remove the `roles_raw` validation; update `AccessTokenPayload` in `application/types.py` to drop `roles`
- [x] 8.3 Update `LoginUser`, `RotateRefreshToken`, and any other caller of `_token_service.issue` to drop the `roles` argument
- [x] 8.4 Update unit tests `src/features/auth/tests/unit/test_jwt_leeway.py` (didn't reference roles; coverage in `test_token_no_roles_claim.py`)
- [x] 8.5 Confirm legacy tokens with stray `roles` claims still decode (`test_legacy_token_with_roles_claim_still_decodes`)

## 9. Auth admin HTTP routes pruning

- [x] 9.1 Remove handlers from `adapters/inbound/http/admin.py`: `create_role`, `patch_role`, `list_roles`, `create_permission`, `list_permissions`, `add_role_permission`, `remove_role_permission`, `add_user_role`, `remove_user_role`
- [x] 9.2 Re-gate `list_users` with `require_authorization("manage_users", "system", None)`
- [x] 9.3 Re-gate `list_audit_log` with `require_authorization("read_audit", "system", None)`
- [x] 9.4 Remove now-unused schemas from `adapters/inbound/http/schemas.py`: `RoleCreate`, `RoleUpdate`, `RoleRead`, `PermissionCreate`, `PermissionRead`, `PermissionAssignmentRequest`, `UserRoleAssignmentRequest`
- [x] 9.5 Update `adapters/inbound/http/dependencies.py` if it imported `require_permissions` (rewritten to drop RBAC helpers)
- [x] 9.6 Update `adapters/inbound/http/router.py` exports (no changes required)

## 10. Auth container wiring

- [x] 10.1 Update `src/features/auth/composition/container.py` to drop the deleted use case fields (list_roles, create_role, update_role, list_permissions, create_permission, assign_role_permission, remove_role_permission, assign_user_role, remove_user_role, seed_initial_data, bootstrap_super_admin → bootstrap_system_admin)
- [x] 10.2 Add a new field `authorization: AuthorizationPort` and wire `SQLModelAuthorizationAdapter` from the same engine the repo uses
- [x] 10.3 Update `_shutdown` to dispose any new resources (no new disposable resources; authorization adapter shares repo engine)
- [x] 10.4 Update `composition/wiring.py` if mount order or attached state changed (publishes `app.state.authorization` for the platform dependency)

## 11. Kanban: write the owner tuple on board create

- [x] 11.1 Update `application/use_cases/board/create_board.py` to take an `AuthorizationPort` dependency (now consumed via `uow.authorization`)
- [x] 11.2 After `uow.commands.save(board)`, call `auth.write_relationships([Relationship("kanban", board.id, "owner", "user", str(actor_id))])` inside the same transaction
- [x] 11.3 Update `application/ports/outbound/unit_of_work.py` to expose an `authorization` accessor that returns a session-scoped `AuthorizationPort` for transactional writes
- [x] 11.4 Implement the session-scoped variant in `adapters/outbound/persistence/sqlmodel/unit_of_work.py` (uses the same Session as the kanban writes)
- [x] 11.5 Update `composition/container.py:KanbanContainer.create_board_use_case` to inject the port (UoW exposes session-scoped `authorization`)
- [x] 11.6 Add a unit test asserting that a failure during relationship write rolls back the board insert (`test_relationship_write_failure_rolls_back_the_board_insert`)

## 12. Kanban: list filters via `lookup_resources`

- [x] 12.1 Update `application/use_cases/board/list_boards.py` to take `AuthorizationPort` and the current actor id
- [x] 12.2 Resolve readable board ids via `auth.lookup_resources(actor_id, "read", "kanban")`
- [x] 12.3 Pass the id list to the query repository via a new `list_by_ids` method (add to `KanbanQueryRepositoryPort` and the SQLModel view)
- [x] 12.4 Wire the actor id from the request through the use case; update `dependencies.py` and `boards.py`
- [x] 12.5 Add unit tests for empty access, partial access, and full access cases (`test_list_boards_authz_filter.py`)

## 13. Kanban: route gating

- [x] 13.1 Update `src/main.py` to remove `require_permissions("kanban:read"/"kanban:write")` from `mount_kanban_routes` arguments; pass empty dependency lists or remove the parameter
- [x] 13.2 In each kanban HTTP route, add the appropriate `require_authorization` to the route decorator's `dependencies=[...]`
- [x] 13.3 Decide and document: do column/card routes use resource_type="kanban" with a precomputed board id, or resource_type="column"/"card" with engine-side walk? Chose engine-side walk via `resource_type="column"`/`"card"` — keeps routes free of repository lookups and lets the parent-walk logic stay in one place.
- [x] 13.4 Verify `POST /boards` and `GET /boards` have NO `require_authorization` (creation is open; listing filters internally)

## 14. Tests: drop RBAC suites

- [x] 14.1 Delete `src/features/auth/tests/unit/test_assign_role.py`
- [x] 14.2 Delete `src/features/auth/tests/unit/test_grant_permission.py`
- [x] 14.3 Delete `src/features/auth/tests/e2e/test_rbac_admin.py`
- [x] 14.4 Delete `src/features/auth/tests/integration/test_rbac_cache_invalidation.py`
- [x] 14.5 Update `src/features/auth/tests/fakes/fake_auth_repository.py` to drop role/permission methods and the `roles`/`permissions` fields on the principal
- [x] 14.6 Update remaining auth tests that assert on `roles` claim or principal `roles`/`permissions` fields (rewrote `test_stale_token_returns_401`, `test_missing_token_is_401_and_user_without_authz_is_403`; updated kanban e2e tests for ReBAC 403 semantics)

## 15. Tests: ReBAC engine and port

- [x] 15.1 Add `src/features/auth/tests/unit/test_authorization_actions_map.py`: every `ACTIONS[resource_type][action]` is a non-empty frozenset of valid relations; unknown pair raises
- [x] 15.2 Add `src/features/auth/tests/unit/test_authorization_hierarchy.py`: `expand_relations` covers owner→{owner,writer,reader}, writer→{writer,reader}, reader→{reader}
- [x] 15.3 Add `src/features/auth/tests/unit/test_authorization_engine_check.py`: board-level checks, hierarchy implications
- [x] 15.4 Add `src/features/auth/tests/unit/test_authorization_engine_inheritance.py`: card and column checks resolve via parent-board walk; missing parent returns False without raising
- [x] 15.5 Add `src/features/auth/tests/unit/test_authorization_lookup.py`: lookup_resources/lookup_subjects, hierarchy, pagination
- [x] 15.6 Add `src/features/auth/tests/integration/test_relationship_repository.py` (testcontainers): CRUD, unique constraint idempotency, indexes used by EXPLAIN, lookup_resources query plan
- [x] 15.7 Add `src/features/auth/tests/contracts/authorization_contract.py` and run it against the in-memory fake and the real adapter

## 16. Tests: HTTP authorization and bootstrap

- [x] 16.1 Add `src/features/auth/tests/e2e/test_bootstrap_system_admin.py`: env-var bootstrap creates the user and the system tuple; second run is idempotent
- [x] 16.2 Add `src/features/auth/tests/e2e/test_admin_routes_authz.py`: non-admin gets 403; admin gets 200 on `/admin/users` and `/admin/audit-log`
- [x] 16.3 Add `src/features/kanban/tests/e2e/test_kanban_authorization_flow.py`: register user → admin grants writer on board → user can PATCH but not DELETE → admin grants owner → user can DELETE; non-readers get 403; non-creators see filtered list on `GET /boards`
- [x] 16.4 Add `src/features/kanban/tests/e2e/test_kanban_card_inheritance.py`: board reader can GET cards; board writer can PATCH cards; card-level routes return 403 for non-readers
- [x] 16.5 Add `src/features/auth/tests/integration/test_migration_round_trip.py`: alembic upgrade head + downgrade -1 + upgrade head leaves an equivalent schema and a usable `relationships` table

## 17. Tests: token shape and cache invalidation

- [x] 17.1 Add unit test that `AccessTokenService.issue(...)` produces a payload with no `roles` key (`test_token_no_roles_claim.py`)
- [x] 17.2 Add unit test that legacy tokens carrying a `roles` claim still decode (claim is ignored)
- [x] 17.3 Unit + integration tests that writing/deleting a relationship for user U bumps `User.authz_version` (`test_authz_version_invalidation.py`, `test_relationship_repository.py::test_authz_version_bumps_on_write_against_postgres`)

## 18. Quality gates and documentation

- [x] 18.1 Update `pyproject.toml` import-linter contracts if any layer references changed (no contract changes needed — kanban → auth.application.authorization passed under the existing inward-dependency rules; all 12 contracts kept)
- [x] 18.2 Run `make quality` (lint + arch + typecheck) and fix issues — ruff, lint-imports, mypy all clean
- [x] 18.3 Run `make test` and `make test-integration` — 216 passed (195 unit/e2e + 21 integration), 0 failing
- [x] 18.4 Run `make ci` end-to-end — quality + test + integration all green
- [x] 18.5 Update the SpiceDB adapter's README with final wording
- [x] 18.6 Confirm CLAUDE.md is NOT updated in this change (deferred to follow-up `template-quality-cleanups` proposal)

## 19. Manual verification

- [x] 19.1 Fresh setup: docker compose down -v + up --build with a clean Postgres volume; migrations ran cleanly to head; only the relationships table exists alongside the user/audit/token tables (no roles/permissions/role_permissions/user_roles)
- [x] 19.2 Bootstrap created `root@example.com` (authz_version=2) and exactly one `system:main#admin@user:{root_id}` tuple; audit event `authz.bootstrap_admin_assigned` was recorded
- [x] 19.3 Admin login → `/admin/users` 200, `/admin/audit-log` 200; JWT carries only `sub/exp/iat/nbf/jti/authz_version` (no roles claim)
- [x] 19.4 Registered alice; alice's `/admin/users` → 403; anonymous → 401
- [x] 19.5 Alice POST /boards → 201, owner tuple written; column create + card create + GET card + PATCH card all 200 via parent-walk; DELETE board → 204
- [x] 19.6 Admin's `GET /boards` returns `[]` (no kanban relations); admin's GET on alice's board → 403; admin's POST column on alice's board → 403

### Bug found and fixed during manual verification

The auth container's `SQLModelAuthorizationAdapter` was constructed without a `parent_resolver`, so HTTP-layer checks on `column`/`card` resources couldn't walk to the parent board (returned 403 even for the owner). Added `set_parent_resolver()` to the adapter and a `parent_resolver` field on `KanbanContainer`; `main.py` lifespan now wires kanban's resolver back into auth's adapter after both containers are built. Duck-typed via `getattr` so adapters that resolve inheritance natively (SpiceDB) skip the hook.
