## 1. Pre-flight

- [ ] 1.1 Confirm `decouple-authz-from-features` has been merged and archived (this proposal depends on the registry-driven model)
- [ ] 1.2 Ensure `make ci` is green on the base branch before starting the move
- [ ] 1.3 Snapshot the current import-linter contract list so the new contracts can be added cleanly

## 2. Move the relationships table to the platform layer

- [ ] 2.1 Create `src/platform/persistence/sqlmodel/authorization/__init__.py` and `models.py`
- [ ] 2.2 Move the `RelationshipTable` SQLModel definition from `src/features/auth/adapters/outbound/persistence/sqlmodel/models.py` to the platform module unchanged
- [ ] 2.3 Update every importer to point at the new platform path; ripgrep `RelationshipTable` to confirm
- [ ] 2.4 Add an empty Alembic migration `alembic/versions/<date>_<rev>_relationships_table_moves_to_platform.py` whose `upgrade()` and `downgrade()` are no-ops; comment explains the move
- [ ] 2.5 Update `alembic/env.py` if metadata sources change (the table registers under `SQLModel.metadata` regardless of module; verify by running `alembic upgrade head` from a fresh DB)
- [ ] 2.6 Run integration tests; ensure the migration round-trip test still passes

## 3. Scaffold the authorization feature slice

- [ ] 3.1 Create `src/features/authorization/{application,adapters,composition,tests}/__init__.py`
- [ ] 3.2 Mirror the `_template` feature's structure for the inner directories (`application/{ports,use_cases}`, `adapters/outbound/{sqlmodel,spicedb}`, `composition`)
- [ ] 3.3 Add `src/features/authorization/composition/app_state.py` with `set_authorization_container`/`get_authorization_container` helpers if the feature exposes its container on `app.state`
- [ ] 3.4 Add an `__init__.py` re-exporting the public surface (`AuthorizationPort`, `AuthorizationRegistry`, `Relationship`, `BootstrapSystemAdmin`)

## 4. Move the engine, registry, and bootstrap into the new feature

- [ ] 4.1 Move `application/authorization/{ports.py,actions.py,hierarchy.py,resource_graph.py,types.py,errors.py,registry.py}` from `features/auth/` to `features/authorization/application/`
- [ ] 4.2 Move `adapters/outbound/authorization/sqlmodel/` and `adapters/outbound/authorization/spicedb/` to `features/authorization/adapters/outbound/`
- [ ] 4.3 Move `application/use_cases/admin/bootstrap_admin.py` (`BootstrapSystemAdmin`) to `features/authorization/application/use_cases/bootstrap_system_admin.py`
- [ ] 4.4 Update every import path; ripgrep on `from src.features.auth.application.authorization` and `from src.features.auth.adapters.outbound.authorization` to find leftover imports
- [ ] 4.5 Update `features/auth/composition/container.py` to drop authorization-related fields (registry, authorization, bootstrap_system_admin)

## 5. Define the new outbound ports in authorization

- [ ] 5.1 Add `features/authorization/application/ports/outbound/user_authz_version_port.py` with the `UserAuthzVersionPort` Protocol (`bump(user_id: UUID) -> None`)
- [ ] 5.2 Add `features/authorization/application/ports/outbound/user_registrar_port.py` with the `UserRegistrarPort` Protocol (`register_or_lookup(email: str, password: str) -> UUID`)
- [ ] 5.3 Add `features/authorization/application/ports/outbound/audit_port.py` with the `AuditPort` Protocol (`record(event_type: str, *, user_id: UUID | None = None, metadata: dict | None = None) -> None`)
- [ ] 5.4 Update `BootstrapSystemAdmin` to consume `UserRegistrarPort` instead of `RegisterUser`, and `AuditPort` instead of the auth repository
- [ ] 5.5 Update `SQLModelAuthorizationAdapter.write_relationships` and `delete_relationships` to call `UserAuthzVersionPort.bump(...)` instead of mutating the users table directly
- [ ] 5.6 Drop the existing `_bump_authz_version_for(session, user_ids)` helper and the direct `UserTable` import from the adapter

## 6. Implement the ports in the auth feature

- [ ] 6.1 Add `features/auth/adapters/outbound/authz_version/__init__.py` and `sqlmodel.py` with `SQLModelUserAuthzVersionAdapter` (takes the engine; runs `UPDATE users SET authz_version = authz_version + 1, updated_at = now() WHERE id = :id`)
- [ ] 6.2 Add a session-scoped variant (`SessionSQLModelUserAuthzVersionAdapter`) that takes a borrowed Session, so kanban's UoW can commit board-create + owner-tuple-write + version-bump atomically
- [ ] 6.3 Add `features/auth/adapters/outbound/user_registrar/sqlmodel.py` with `SQLModelUserRegistrarAdapter` composing the existing `RegisterUser` use case and `get_user_by_email` lookup
- [ ] 6.4 Add `features/auth/adapters/outbound/audit/sqlmodel.py` with `SQLModelAuditAdapter` calling the existing `record_audit_event` repository method
- [ ] 6.5 Wire all three adapters in `features/auth/composition/container.py`, exposing them on the container so `main.py` can pass them across to authorization

## 7. Build the authorization container

- [ ] 7.1 Add `features/authorization/composition/container.py` with `AuthorizationContainer` (fields: `port: AuthorizationPort`, `registry: AuthorizationRegistry`, `bootstrap_system_admin: BootstrapSystemAdmin`, `shutdown: Callable[[], None]`)
- [ ] 7.2 Add `build_authorization_container(*, engine: Engine, user_authz_version: UserAuthzVersionPort, user_registrar: UserRegistrarPort, audit: AuditPort, settings: AppSettings) -> AuthorizationContainer`
- [ ] 7.3 Inside the builder: construct the registry pre-populated with `system`, build the SQLModel adapter, build `BootstrapSystemAdmin`
- [ ] 7.4 Add `features/authorization/composition/wiring.py` with `attach_authorization_container(app, container)` that publishes `app.state.authorization = container.port` (preserves the platform-level dependency contract)

## 8. Wire everything in main.py

- [ ] 8.1 In `src/main.py:lifespan`, build the auth container as today (no authorization concerns)
- [ ] 8.2 Build the authorization container, passing `auth.user_authz_version_adapter`, `auth.user_registrar_adapter`, and `auth.audit_adapter`
- [ ] 8.3 Run `_run_auth_bootstrap` against `authorization.bootstrap_system_admin` (not `auth.bootstrap_system_admin` anymore)
- [ ] 8.4 Build the kanban container, passing `authorization.port` and `authorization.registry`
- [ ] 8.5 Call `register_kanban_authorization(authorization.registry, kanban_lookup)` after both containers exist
- [ ] 8.6 Seal the registry before yielding from lifespan
- [ ] 8.7 Update shutdown order: kanban → authorization → auth (reverse of build order)

## 9. Layering enforcement

- [ ] 9.1 Add the three Import Linter contracts in `pyproject.toml` (`auth ↛ authorization`, `authorization ↛ auth`, `kanban ↛ auth`)
- [ ] 9.2 Run `make lint-arch`; fix any contract violations by routing through ports instead of direct imports
- [ ] 9.3 Add an explicit unit test under `src/platform/tests/test_authorization_layering.py` that walks `src/features/{auth,authorization,kanban}` ASTs and asserts no cross-imports outside of allowed `platform` and `application/ports/outbound` paths (belt-and-braces; import-linter is the primary check)

## 10. Tests

- [ ] 10.1 Move `features/auth/tests/unit/test_authorization_*` to `features/authorization/tests/unit/`
- [ ] 10.2 Move `features/auth/tests/unit/test_authz_version_invalidation.py` to `features/authorization/tests/unit/`; rewrite it to use a fake `UserAuthzVersionPort` and a real adapter against SQLite
- [ ] 10.3 Move `features/auth/tests/unit/test_authorization_contract_*` to `features/authorization/tests/unit/`
- [ ] 10.4 Move `features/auth/tests/integration/test_relationship_repository.py` to `features/authorization/tests/integration/`
- [ ] 10.5 Move `features/auth/tests/integration/test_migration_round_trip.py` to `features/authorization/tests/integration/`; update the no-op-migration assertion
- [ ] 10.6 Move `features/auth/tests/e2e/test_bootstrap_system_admin.py` to `features/authorization/tests/e2e/`
- [ ] 10.7 Move `features/auth/tests/e2e/test_admin_routes_authz.py` — keep it under auth (it tests auth's admin routes); update fixtures to spin up the authorization container too
- [ ] 10.8 Update `features/auth/tests/e2e/conftest.py` to build both containers and wire the ports
- [ ] 10.9 Update `features/kanban/tests/e2e/conftest.py` to construct an authorization container with a fake `UserAuthzVersionPort`/`UserRegistrarPort`/`AuditPort` so the kanban tests don't pull in the auth feature
- [ ] 10.10 Add a unit test for `SQLModelUserAuthzVersionAdapter`: bump-then-read shows authz_version + 1
- [ ] 10.11 Add a unit test for `SQLModelUserRegistrarAdapter`: idempotent on email
- [ ] 10.12 Add a contract test under `features/authorization/tests/contracts/` that validates the three new ports against an in-memory fake and the SQLModel adapter

## 11. Documentation

- [ ] 11.1 Update CLAUDE.md to describe the three-feature layout (auth, authorization, kanban) with one paragraph per feature explaining what it owns and what ports it consumes from peers
- [ ] 11.2 Update CLAUDE.md's Layer Contracts section: add the three new contracts; remove the "auth → authorization is allowed" implicit allowance
- [ ] 11.3 Update the SpiceDB stub README to reflect the new module path (`features/authorization/adapters/outbound/spicedb/`)
- [ ] 11.4 Add a brief "Adding a new feature" section to CLAUDE.md showing how to register actions/relations/parent walks against the authorization registry from the new feature's composition root

## 12. Quality gates

- [ ] 12.1 Run `make lint-arch` (12 contracts → 15 contracts now); confirm all kept
- [ ] 12.2 Run `make lint`, `make typecheck`, `make format`
- [ ] 12.3 Run `make test` (unit + e2e)
- [ ] 12.4 Run `make test-integration`
- [ ] 12.5 Run `make ci` end-to-end

## 13. Manual verification

- [ ] 13.1 `docker compose down -v && docker compose up -d --build`
- [ ] 13.2 Confirm bootstrap creates the system-admin tuple; verify by `psql` against the relationships table
- [ ] 13.3 Run the same curl flow as the rebac-authorization manual verification (admin login → /admin/users 200; alice register + login → /admin/users 403; alice POST /boards → 201; admin GET /api/boards → []; alice card chain through parent walk → 200; admin denials → 403)
- [ ] 13.4 Confirm `auth_audit_events` shows `auth.user_registered`, `authz.bootstrap_admin_assigned`, `auth.login_succeeded` events with the same shape as before
- [ ] 13.5 Verify nothing in the API or wire format changed (a client written against the previous version still works)
