## 1. Introduce the AuthorizationRegistry

- [x] 1.1 Add `src/features/auth/application/authorization/registry.py` with the `AuthorizationRegistry` class implementing `register_resource_type`, `register_parent`, `seal`, and the read methods (`relations_for`, `expand_relations`, `parent_of`, `has_stored_relations`)
- [x] 1.2 Make `AuthorizationRegistry` raise `ValueError` on duplicate registrations (same `resource_type` registered twice with either method)
- [x] 1.3 Make every register method raise `RuntimeError` once `seal()` has been called
- [x] 1.4 Track inheritance in `register_parent` so `relations_for("card", "read")` chains up to `kanban`'s registered actions
- [x] 1.5 Expose introspection (`registered_resource_types() -> set[str]`) for startup logging and tests
- [x] 1.6 Add unit tests covering: register-then-lookup, duplicate registration error, seal-then-register error, multi-level inheritance lookup

## 2. Adapt the engine to use the registry

- [x] 2.1 Add a registry argument to `SQLModelAuthorizationAdapter.__init__` and `SessionSQLModelAuthorizationAdapter.__init__` (and to `_BaseAuthorizationAdapter.__init__`)
- [x] 2.2 Rewrite `check()` to walk parents via `registry.parent_of` until `registry.has_stored_relations(walked_type)` is `True`, then evaluate against the original action's required relations expanded under the parent type's hierarchy
- [x] 2.3 Rewrite `lookup_resources()` to read the action map via `registry.relations_for` and the hierarchy expansion via `registry.expand_relations`; remove the special-case redirect for column/card resource types
- [x] 2.4 Drop the hardcoded `_resolve_to_board` and the explicit `if resource_type in {"card", "column"}` branch; the walker now handles arbitrary depth
- [x] 2.5 Verify no string `"kanban"`, `"column"`, or `"card"` remains anywhere under `src/features/auth/application/authorization/` or `src/features/auth/adapters/outbound/authorization/sqlmodel/` (ripgrep check)

## 3. Replace the static actions and hierarchy modules

- [x] 3.1 Delete the constants `KANBAN_ACTIONS`, `KANBAN_RELATION_HIERARCHY`, `SYSTEM_ACTIONS`, `SYSTEM_RELATION_HIERARCHY`, and the `ACTIONS`/`_HIERARCHIES` maps from `actions.py` and `hierarchy.py`
- [x] 3.2 Replace `actions.relations_for` and `hierarchy.expand_relations` with thin wrappers that delegate to the registry (so existing call sites keep their import paths)
- [x] 3.3 Update `application/authorization/__init__.py` exports to remove the deleted constants and add `AuthorizationRegistry`
- [x] 3.4 Remove the `ParentResolver.board_id_for_card` and `board_id_for_column` methods from `resource_graph.py`; keep only a single `parent_of(resource_type, resource_id) -> tuple[str, str] | None` Protocol method
- [x] 3.5 Drop `resolve_board_id` (no longer needed; the engine walks via the registry)

## 4. Auth container pre-registers system

- [x] 4.1 In `build_auth_container`, construct a fresh `AuthorizationRegistry` and call `register_resource_type("system", ...)` with `manage_users` and `read_audit` actions
- [x] 4.2 Add a `registry: AuthorizationRegistry` field to `AuthContainer` and assign the constructed registry
- [x] 4.3 Pass the registry into `SQLModelAuthorizationAdapter` so the engine has read access
- [x] 4.4 Move `set_parent_resolver` off the adapter; the registry is now the seam (the adapter reads `parent_of` from the registry directly)

## 5. Kanban registers its resource types from composition

- [x] 5.1 In `src/features/kanban/composition/wiring.py`, add a `register_kanban_authorization(registry, lookup_repo)` function that calls `registry.register_resource_type("kanban", ...)` with the kanban actions and hierarchy
- [x] 5.2 Within the same function, call `registry.register_parent("column", parent_of=..., inherits_from="kanban")` where the lambda returns `("kanban", lookup.find_board_id_by_column(column_id))`
- [x] 5.3 Within the same function, call `registry.register_parent("card", parent_of=..., inherits_from="column")` so multi-level walks work
- [x] 5.4 Update `build_kanban_container` to accept the registry and call the registration function as part of its construction
- [x] 5.5 Drop the `parent_resolver` field from `KanbanContainer` (the registry holds it now); drop `_LookupParentResolver` from container.py
- [x] 5.6 Update `SqlModelUnitOfWork` to construct its session-scoped authorization adapter with the registry, not a separate parent resolver

## 6. Composition root wiring

- [x] 6.1 Update `src/main.py` lifespan: build auth → call `register_kanban_authorization(auth.registry, kanban_lookup)` → build kanban → call `auth.registry.seal()` before yielding
- [x] 6.2 Remove the `getattr(..., "set_parent_resolver", None)` hook in main.py — the seam moved to the registry
- [x] 6.3 Update test fixtures (`src/features/kanban/tests/e2e/conftest.py`) to construct a registry, register kanban there, and pass it through

## 7. Tests

- [x] 7.1 Add `src/features/auth/tests/unit/test_authorization_registry.py` covering registration, sealing, duplicate-detection, and inheritance lookups
- [x] 7.2 Migrate `test_authorization_actions_map.py` to assert against a registry seeded by a helper instead of static constants
- [x] 7.3 Migrate `test_authorization_hierarchy.py` similarly
- [x] 7.4 Migrate `test_authorization_engine_check.py` and `test_authorization_engine_inheritance.py` to inject a registry-backed adapter
- [x] 7.5 Migrate `test_authorization_lookup.py` to use the registry
- [x] 7.6 Update `test_authz_version_invalidation.py` if its setup touched the deleted constants
- [x] 7.7 Add a static check (a unit test, or an import-linter contract) that asserts no source file under `src/features/auth/application/authorization/` mentions kanban-flavoured resource type strings
- [x] 7.8 Add a unit test that calling `check` with an unregistered resource type raises `UnknownActionError`

## 8. Quality gates and documentation

- [x] 8.1 Update `src/features/auth/adapters/outbound/authorization/spicedb/README.md` to describe the registration model in the migration narrative
- [x] 8.2 Run `make quality` and fix any issues
- [x] 8.3 Run `make test` and `make test-integration`; fix until green
- [x] 8.4 Confirm CLAUDE.md does NOT need updating for this change (the only externally visible difference is internal — feature wiring; no new env vars or routes)
- [x] 8.5 Manual smoke: bring up Docker, run the same flow as the rebac-authorization manual verification (bootstrap → admin → register alice → alice creates board+column+card → admin gets 403). Confirm identical behavior.
