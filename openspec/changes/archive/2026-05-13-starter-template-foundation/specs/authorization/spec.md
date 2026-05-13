## MODIFIED Requirements

### Requirement: AuthorizationPort defines the application-side authorization contract

The system SHALL expose an `AuthorizationPort` Protocol — in `src/features/authorization/application/ports/` — that the application layer calls for every authorization decision. The port SHALL define exactly five methods: `check`, `lookup_resources`, `lookup_subjects`, `write_relationships`, and `delete_relationships`. Adapters SHALL implement this port, and the application layer SHALL never depend on a concrete adapter type. The port and its adapters SHALL live entirely inside the authorization feature; every consumer feature (authentication, users, the live `_template`, and any user-added feature) depends on the port, never on the implementation.

#### Scenario: Application code depends only on the port

- **WHEN** any use case in any feature performs an authorization decision
- **THEN** the use case takes an `AuthorizationPort` as a constructor dependency
- **AND** no module under `application/` of any feature imports from `adapters/outbound/` of any feature

#### Scenario: Two adapters implement the port

- **WHEN** the codebase is loaded
- **THEN** `SQLModelAuthorizationAdapter` (under `src/features/authorization/adapters/outbound/sqlmodel/`) implements `AuthorizationPort`
- **AND** `SpiceDBAuthorizationAdapter` (under `src/features/authorization/adapters/outbound/spicedb/`) implements `AuthorizationPort`
- **AND** the SpiceDB adapter raises `NotImplementedError` from each method with a message pointing to its README

### Requirement: Authorization is a self-contained feature slice

The system SHALL host authorization concerns in a dedicated feature slice at `src/features/authorization/`. The slice SHALL contain the `AuthorizationPort`, the `AuthorizationRegistry`, the SQLModel adapter, the SpiceDB stub, the outbound port definitions (`UserAuthzVersionPort`, `UserRegistrarPort`, `AuditPort`), and the `BootstrapSystemAdmin` use case. The slice SHALL NOT import from any other feature.

#### Scenario: Authorization owns the engine code

- **WHEN** the codebase is loaded
- **THEN** `src/features/authorization/` contains the engine, registry, ports, and bootstrap
- **AND** `src/features/authentication/` and `src/features/users/` do NOT contain any of those

#### Scenario: Authorization does not import from any other feature

- **WHEN** the codebase is loaded
- **THEN** no module under `src/features/authorization/` imports from `src/features/authentication/`, `src/features/users/`, `src/features/email/`, `src/features/background_jobs/`, `src/features/file_storage/`, or `src/features/_template/`
- **AND** the import-linter contract "Authorization is independent of every other feature" passes

### Requirement: Cache invalidation flows through UserAuthzVersionPort

Authorization SHALL bump `User.authz_version` after any `write_relationships` or `delete_relationships` call that touches a `user` subject by calling `UserAuthzVersionPort.bump(user_id)`. The port is defined in `src/features/authorization/application/ports/outbound/` and is implemented by an adapter in the users feature (formerly the authentication feature).

#### Scenario: A relationship write triggers a port call per affected user subject

- **GIVEN** a relationships write batch with two distinct user subjects `u1` and `u2`
- **WHEN** `write_relationships(...)` returns
- **THEN** `UserAuthzVersionPort.bump` was called once with `u1` and once with `u2`

#### Scenario: Non-user subjects do not trigger the port

- **WHEN** a write contains only `service`-typed subjects
- **THEN** `UserAuthzVersionPort.bump` is not called

#### Scenario: The bump is dispatched to the users-feature adapter

- **WHEN** the application is composed
- **THEN** the `UserAuthzVersionPort` instance wired into the authorization container is an instance of `src.features.users.adapters.outbound.authz_version.SQLModelUserAuthzVersionAdapter`
- **AND** no authentication-feature adapter is wired into this port

### Requirement: Bootstrap depends on UserRegistrarPort

The `BootstrapSystemAdmin` use case SHALL live in `src/features/authorization/application/use_cases/` and SHALL depend on `UserRegistrarPort` (defined in authorization's outbound ports) and `AuditPort`. It SHALL NOT import `RegisterUser` or any other authentication- or users-feature symbol directly. The concrete `UserRegistrarPort` implementation SHALL come from the users feature.

#### Scenario: Bootstrap composes user registration through the port

- **WHEN** `BootstrapSystemAdmin.execute(email, password)` runs
- **THEN** the use case calls `UserRegistrarPort.register_or_lookup(email=..., password=...)`
- **AND** the returned `user_id` is used to write the system-admin tuple
- **AND** the use case writes one audit event of type `authz.bootstrap_admin_assigned` via the `AuditPort`

#### Scenario: The wired adapter comes from users

- **WHEN** the application is composed
- **THEN** the `UserRegistrarPort` instance wired into the authorization container is an instance of `src.features.users.adapters.outbound.user_registrar.SQLModelUserRegistrarAdapter`

### Requirement: Layering is enforced by Import Linter

The `pyproject.toml` SHALL declare the following forbidden import contracts, each verified by `make lint-arch`:

- `authentication ↛ authorization`
- `authorization ↛ authentication`
- `users ↛ authentication`
- `users ↛ authorization (adapters)` — users may import the authorization *ports* package but not the adapters
- `authentication ↛ users (adapters)` — authentication may import only the `UserPort` from users
- Every feature ↛ every other feature's `adapters/outbound/` directly
- `platform ↛ features` (unchanged)

#### Scenario: The contracts are present and pass

- **WHEN** `uv run lint-imports` is invoked
- **THEN** the contracts listed above are all present in the output
- **AND** all are reported as KEPT

## ADDED Requirements

### Requirement: The live `_template` feature registers a `thing` resource type with the authorization registry

The live `_template` feature SHALL register the resource type `thing` with the authorization registry, declaring three relations (`owner`, `writer`, `reader`) with the hierarchy `owner ⊇ writer ⊇ reader`. The actions `read`, `update`, and `delete` SHALL map to `frozenset({"reader", "writer", "owner"})`, `frozenset({"writer", "owner"})`, and `frozenset({"owner"})` respectively. The `thing` type SHALL have no parent-walk; it is a leaf type.

#### Scenario: Template registers its resource type

- **WHEN** `build_template_container(authorization=..., registry=...)` returns
- **THEN** `registry.has_stored_relations("thing")` returns `True`
- **AND** `registry.relations_for("thing", "read")` returns `frozenset({"reader", "writer", "owner"})`

#### Scenario: Creating a thing grants the creator the owner relation

- **WHEN** user `u1` calls `POST /things` with a valid body and the call succeeds
- **THEN** a tuple `thing:{thing.id}#owner@user:u1` exists in the relationships table
- **AND** `u1.authz_version` is one greater than its prior value

## REMOVED Requirements

### Requirement: Kanban defines an owner ⊇ writer ⊇ reader hierarchy on board resources

**Reason**: The kanban feature is removed from the main branch. It is preserved on the `examples/kanban` branch as a reference for ReBAC with parent-walk hierarchies. The hierarchy pattern itself is preserved by the new `thing` resource type registered by the live `_template`.

**Migration**: Consumers wanting to see this exact pattern in action can check out `examples/kanban`. New features model their own hierarchies via the authorization registry's `register_resource_type` and `register_parent` API, which is unchanged.

### Requirement: Cards and columns inherit relations from their parent board

**Reason**: Kanban removal (see above). The parent-walk mechanism in `SQLModelAuthorizationAdapter.check` is unchanged and remains exercised by tests that use a synthetic `parent-of-parent` fixture rather than card/column.

**Migration**: The contract for parent-walk resolution is now covered by the authorization adapter's contract tests using synthetic resource types (`type_a → type_b → type_c`). The behavior on the real schema is unchanged.

### Requirement: Listing kanban boards filters at the authorization layer

**Reason**: Kanban removal. The equivalent pattern is demonstrated by `GET /things` in the live `_template` feature, which calls `lookup_resources(user_id, "read", "thing")` and fetches only the returned ids.

**Migration**: See `_template/things` for the canonical "list resources the caller can see" example. The `lookup_resources` port contract is unchanged.

### Requirement: Creating a board grants the actor the owner relation

**Reason**: Kanban removal. The equivalent pattern is covered by the new "Creating a thing grants the creator the owner relation" scenario above.

**Migration**: See `_template/things` for the canonical "creator becomes owner" pattern, including the unit-of-work participation that ensures the relationship write rolls back with the resource write.

### Requirement: Action-to-relation dispatch is defined in `application/authorization/actions.py`

**Reason**: This requirement encoded a static `ACTIONS` map with hard-coded kanban entries. The runtime `AuthorizationRegistry` (introduced by the `decouple-authz-from-features` change) is now the single source of truth and supersedes the static map. Feature-specific dispatch entries (`kanban`, `column`, `card`) are removed with the feature.

**Migration**: Features register their actions via `registry.register_resource_type(<type>, actions={...}, hierarchy={...})` at composition. No static map is consulted at check time.

### Requirement: Auth pre-registers only the system resource type

**Reason**: The feature is renamed from `auth` to `authentication`. The behavior is unchanged — registration of `system` still happens at the authentication container's construction.

**Migration**: Replace this requirement with the renamed equivalent: "Authentication pre-registers only the system resource type" (covered implicitly by the authentication spec's self-containment requirement; no separate scenario needed because the registry assertion is verified by the registry's own scenarios).
