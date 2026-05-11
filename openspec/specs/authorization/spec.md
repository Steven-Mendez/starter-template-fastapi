# authorization Specification

## Purpose
TBD - created by archiving change rebac-authorization. Update Purpose after archive.
## Requirements
### Requirement: AuthorizationPort defines the application-side authorization contract

The system SHALL expose an `AuthorizationPort` Protocol in `application/authorization/ports.py` that the application layer calls for every authorization decision. The port SHALL define exactly five methods: `check`, `lookup_resources`, `lookup_subjects`, `write_relationships`, and `delete_relationships`. Adapters SHALL implement this port, and the application layer SHALL never depend on a concrete adapter type.

#### Scenario: Application code depends only on the port

- **WHEN** any use case under `src/features/auth/application/` or `src/features/kanban/application/` performs an authorization decision
- **THEN** the use case takes an `AuthorizationPort` as a constructor dependency
- **AND** no module under `application/` imports from `adapters/outbound/authorization/`

#### Scenario: Two adapters implement the port

- **WHEN** the codebase is loaded
- **THEN** `SQLModelAuthorizationAdapter` (under `adapters/outbound/authorization/sqlmodel/`) implements `AuthorizationPort`
- **AND** `SpiceDBAuthorizationAdapter` (under `adapters/outbound/authorization/spicedb/`) implements `AuthorizationPort`
- **AND** the SpiceDB adapter raises `NotImplementedError` from each method with a message pointing to its README

### Requirement: Relationships are stored as Zanzibar-style 5-tuples

The system SHALL persist authorization state as relationship tuples in a single `relationships` table. Each tuple SHALL identify a subject (a user), a resource (a typed instance), and a relation between them. The table SHALL enforce uniqueness on the full 5-tuple so duplicate writes are no-ops.

#### Scenario: Tuple shape

- **WHEN** a relationship is persisted
- **THEN** the row contains `id`, `resource_type`, `resource_id`, `relation`, `subject_type`, `subject_id`, and `created_at`
- **AND** `(resource_type, resource_id, relation, subject_type, subject_id)` is unique across the table

#### Scenario: Required indexes

- **WHEN** the table is created by migration
- **THEN** an index covers `(resource_type, resource_id, relation)`
- **AND** an index covers `(subject_type, subject_id, resource_type, relation)`

#### Scenario: Duplicate writes are idempotent

- **WHEN** `write_relationships` is called twice for the same tuple
- **THEN** the second call SHALL NOT raise
- **AND** exactly one row exists for that tuple

### Requirement: Kanban defines an owner ⊇ writer ⊇ reader hierarchy on board resources

The kanban resource type SHALL define three relations on board resources: `owner`, `writer`, and `reader`. The hierarchy SHALL be `owner` includes `writer` includes `reader`: a user with the `owner` relation on a board SHALL satisfy any check that requires `writer` or `reader` on that board.

#### Scenario: Owner satisfies writer and reader checks

- **GIVEN** a tuple `kanban:{board_id}#owner@user:{user_id}`
- **WHEN** `check(user_id, "read", ("kanban", board_id))` is called
- **THEN** the result is `True`
- **AND** `check(user_id, "update", ("kanban", board_id))` returns `True`
- **AND** `check(user_id, "delete", ("kanban", board_id))` returns `True`

#### Scenario: Writer satisfies reader and writer but not delete

- **GIVEN** a tuple `kanban:{board_id}#writer@user:{user_id}`
- **WHEN** `check(user_id, "read", ("kanban", board_id))` is called
- **THEN** the result is `True`
- **AND** `check(user_id, "update", ("kanban", board_id))` returns `True`
- **AND** `check(user_id, "delete", ("kanban", board_id))` returns `False`

#### Scenario: Reader satisfies only read

- **GIVEN** a tuple `kanban:{board_id}#reader@user:{user_id}`
- **WHEN** `check(user_id, "update", ("kanban", board_id))` is called
- **THEN** the result is `False`
- **AND** `check(user_id, "delete", ("kanban", board_id))` returns `False`
- **AND** `check(user_id, "read", ("kanban", board_id))` returns `True`

### Requirement: Cards and columns inherit relations from their parent board

Card and column resources SHALL NOT have their own relationship tuples. The `check` method SHALL resolve a card-level or column-level check by walking the parent chain (`card.column_id → column.board_id → board:{id}`) and evaluating the equivalent check on the parent board. The walk SHALL be performed at check time; no inherited tuples SHALL be materialized.

#### Scenario: Reader on the board can read all cards on the board

- **GIVEN** a tuple `kanban:{board_id}#reader@user:{user_id}`
- **AND** a card `card_id` belonging to a column belonging to that board
- **WHEN** `check(user_id, "read", ("card", card_id))` is called
- **THEN** the result is `True`

#### Scenario: Owner on the board can update any card on the board

- **GIVEN** a tuple `kanban:{board_id}#owner@user:{user_id}`
- **AND** a card `card_id` belonging to a column belonging to that board
- **WHEN** `check(user_id, "update", ("card", card_id))` is called
- **THEN** the result is `True`

#### Scenario: No tuples are written for cards or columns when a user is granted board access

- **WHEN** a user is granted `kanban:{board_id}#writer`
- **THEN** the `relationships` table contains exactly one new row, with `resource_type='kanban'`
- **AND** no rows are written with `resource_type='column'` or `resource_type='card'`

#### Scenario: Card check on a card whose parents do not resolve returns False

- **WHEN** `check(user_id, "read", ("card", missing_card_id))` is called and no card with that id exists
- **THEN** the result is `False`
- **AND** the call SHALL NOT raise

### Requirement: System administration is modeled as a relationship on `system:main`

The system SHALL define a `system` resource type with a single global instance whose id is `main`. The `admin` relation on `system:main` SHALL be the only authorization concept used to gate system-level routes. Bootstrap SHALL grant this relation by writing the tuple `system:main#admin@user:{user_id}`.

#### Scenario: Bootstrap writes a single system-admin tuple

- **GIVEN** `APP_AUTH_BOOTSTRAP_SUPER_ADMIN_EMAIL` and `APP_AUTH_BOOTSTRAP_SUPER_ADMIN_PASSWORD` are both set
- **AND** the configured user does not exist
- **WHEN** the application starts and bootstrap runs
- **THEN** the user is created
- **AND** exactly one row exists in `relationships` with `(resource_type='system', resource_id='main', relation='admin', subject_type='user', subject_id=user.id)`
- **AND** an audit event of type `authz.bootstrap_admin_assigned` is recorded for that user

#### Scenario: Bootstrap is idempotent across restarts

- **GIVEN** the bootstrap user already exists with the `system:main#admin` tuple
- **WHEN** the application starts and bootstrap runs again
- **THEN** the second run SHALL NOT create a duplicate user
- **AND** still exactly one matching row exists in `relationships`

#### Scenario: System-level checks dispatch on the main instance

- **WHEN** `check(user_id, "manage_users", ("system", "main"))` is called
- **AND** a tuple `system:main#admin@user:{user_id}` exists
- **THEN** the result is `True`

### Requirement: Action-to-relation dispatch is defined in `application/authorization/actions.py`

The system SHALL define an `ACTIONS: dict[str, dict[str, frozenset[str]]]` map keyed by `resource_type`, then by `action`, whose value is the set of relations that satisfy that action. The map SHALL be the single source of truth for action dispatch. Adding a new action SHALL require only an entry in this map and is SHALL NOT require schema changes.

#### Scenario: Required action mappings exist

- **WHEN** the module `application/authorization/actions.py` is imported
- **THEN** `ACTIONS["kanban"]["read"]` equals `frozenset({"reader", "writer", "owner"})`
- **AND** `ACTIONS["kanban"]["update"]` equals `frozenset({"writer", "owner"})`
- **AND** `ACTIONS["kanban"]["delete"]` equals `frozenset({"owner"})`
- **AND** `ACTIONS["system"]["manage_users"]` equals `frozenset({"admin"})`
- **AND** `ACTIONS["system"]["read_audit"]` equals `frozenset({"admin"})`

#### Scenario: An unknown (resource_type, action) pair is rejected at check time

- **WHEN** `check(user_id, "purge", ("kanban", board_id))` is called and `purge` is not in `ACTIONS["kanban"]`
- **THEN** a `KeyError` is raised
- **OR** a domain `NotAuthorizedError` is raised with a message identifying the missing action

### Requirement: `lookup_resources` returns the resource ids a user has the requested action on

The `AuthorizationPort.lookup_resources(user_id, action, resource_type)` method SHALL return the list of `resource_id` values for which the user satisfies the action's relation set on resources of that type. The method SHALL apply the same hierarchy resolution that `check` uses. Listing SHALL be paginated by an optional `limit` parameter (default 100, maximum 500).

#### Scenario: Lookup returns boards the user has at least reader on

- **GIVEN** tuples `kanban:b1#owner@user:u1`, `kanban:b2#writer@user:u1`, `kanban:b3#reader@user:u1`
- **AND** an additional tuple `kanban:b4#reader@user:u2`
- **WHEN** `lookup_resources(u1, "read", "kanban")` is called
- **THEN** the result contains exactly `b1`, `b2`, and `b3` in some order

#### Scenario: Lookup respects action requirements

- **GIVEN** tuples `kanban:b1#owner@user:u1`, `kanban:b2#writer@user:u1`, `kanban:b3#reader@user:u1`
- **WHEN** `lookup_resources(u1, "delete", "kanban")` is called
- **THEN** the result contains exactly `b1`

#### Scenario: Pagination caps the result size

- **GIVEN** the user has more than 100 readable boards
- **WHEN** `lookup_resources(user_id, "read", "kanban")` is called with the default limit
- **THEN** the result contains at most 100 ids

### Requirement: HTTP routes use `require_authorization` for resource-scoped gating

The platform SHALL expose a `require_authorization(action: str, resource_type: str, id_loader: Callable[[Request], str] | None)` FastAPI dependency. The dependency SHALL resolve the current principal, derive the resource id from the request (or use the sentinel `"main"` when `id_loader` is `None`), call `AuthorizationPort.check`, and raise HTTP 403 on deny.

#### Scenario: Board read endpoint denies non-readers

- **GIVEN** a board `b1` with no relationship tuples for user `u1`
- **WHEN** `u1` calls `GET /boards/b1`
- **THEN** the response status is 403

#### Scenario: Board update endpoint denies readers

- **GIVEN** a tuple `kanban:b1#reader@user:u1`
- **WHEN** `u1` calls `PATCH /boards/b1` with valid body
- **THEN** the response status is 403

#### Scenario: System admin endpoints are gated on `system:main`

- **GIVEN** user `u1` has no tuple on `system:main`
- **WHEN** `u1` calls `GET /admin/users`
- **THEN** the response status is 403
- **AND** when `u1` is later granted `system:main#admin`, the next call returns 200

#### Scenario: 404 vs 403 ordering for missing resources

- **WHEN** a path-bound check is requested for a resource that does not exist
- **THEN** the route SHALL return 403 (not 404), so the API does not reveal resource existence to unauthorized users

### Requirement: Listing kanban boards filters at the authorization layer

`GET /boards` SHALL list only the boards the calling user has at least the `read` action on, by calling `AuthorizationPort.lookup_resources` and then fetching only those boards. The endpoint SHALL NOT return all boards and post-filter.

#### Scenario: Anonymous-equivalent users get an empty list

- **GIVEN** an authenticated user with no relationship tuples on any kanban board
- **WHEN** the user calls `GET /boards`
- **THEN** the response status is 200
- **AND** the response body is an empty list

#### Scenario: Listing returns only authorized boards

- **GIVEN** boards `b1`, `b2`, `b3` exist
- **AND** user `u1` has tuple `kanban:b1#reader@user:u1` and tuple `kanban:b3#owner@user:u1`
- **WHEN** `u1` calls `GET /boards`
- **THEN** the response body contains exactly `b1` and `b3` summaries

### Requirement: Creating a board grants the actor the owner relation

The `POST /boards` route SHALL NOT require any authorization check. After the board is persisted, the system SHALL write a tuple `kanban:{board.id}#owner@user:{actor_id}` and bump `actor.authz_version`. The write SHALL participate in the same unit of work as the board creation so a partial failure cannot leave a board with no owner.

#### Scenario: New board is owned by its creator

- **WHEN** user `u1` calls `POST /boards` with a valid body and the call succeeds
- **THEN** a board row exists with `created_by=u1`
- **AND** a tuple `kanban:{board.id}#owner@user:u1` exists
- **AND** `u1.authz_version` is one greater than its prior value

#### Scenario: Board creation rolls back if relationship write fails

- **GIVEN** the relationship store will reject the next write
- **WHEN** user `u1` calls `POST /boards` with a valid body
- **THEN** no board row is persisted
- **AND** no relationship tuple is persisted

### Requirement: Principal cache invalidates on relationship writes affecting the user

The system SHALL bump `User.authz_version` whenever `write_relationships` or `delete_relationships` operates on a tuple where `subject_type='user'` and `subject_id=U`. The principal cache SHALL key on `(user_id, authz_version)` so the next request from `U` resolves a fresh principal.

#### Scenario: Granting a relation invalidates the cached principal

- **GIVEN** user `u1` has a cached principal at `authz_version=V`
- **WHEN** `write_relationships` writes `kanban:b1#reader@user:u1`
- **THEN** `u1.authz_version` is `V+1`
- **AND** the next request authenticated as `u1` resolves a principal at `authz_version=V+1`

#### Scenario: Revoking a relation invalidates the cached principal

- **GIVEN** user `u1` has a cached principal at `authz_version=V`
- **AND** the tuple `kanban:b1#reader@user:u1` exists
- **WHEN** `delete_relationships` removes that tuple
- **THEN** `u1.authz_version` is `V+1`

### Requirement: JWT access tokens drop the `roles` claim

The `AccessTokenService` SHALL issue tokens whose payload contains exactly `sub`, `exp`, `iat`, `nbf`, `jti`, `authz_version`, and (optionally) `iss`/`aud`. The `roles` claim SHALL NOT be issued. Decoding SHALL NOT require a `roles` claim.

#### Scenario: Issued token has no roles claim

- **WHEN** `AccessTokenService.issue(subject, authz_version)` is called
- **THEN** the decoded payload contains no `roles` key

#### Scenario: Token issued before this change is rejected

- **GIVEN** a JWT issued with the legacy `roles` claim and signed with the current secret
- **WHEN** `AccessTokenService.decode` is called on it
- **THEN** the token is accepted (extra claims are ignored)
- **AND** the resulting `AccessTokenPayload` exposes only `subject`, `authz_version`, `expires_at`, `token_id`

### Requirement: Surviving auth admin endpoints check the system relation

The endpoints `GET /admin/users` and `GET /admin/audit-log` SHALL be gated by `require_authorization` on the `system:main` resource: `manage_users` and `read_audit` respectively. All RBAC-management endpoints (role create/update, permission create, role-permission assign/remove, user-role assign/remove, list roles, list permissions) SHALL be removed.

#### Scenario: Removed RBAC routes return 404

- **WHEN** any client calls `POST /admin/roles`, `PATCH /admin/roles/{id}`, `POST /admin/permissions`, `POST /admin/roles/{id}/permissions`, `DELETE /admin/roles/{id}/permissions/{permission_id}`, `POST /admin/users/{id}/roles`, `DELETE /admin/users/{id}/roles/{role_id}`, `GET /admin/roles`, or `GET /admin/permissions`
- **THEN** the response status is 404

#### Scenario: System admin can list users and read the audit log

- **GIVEN** user `u1` holds `system:main#admin@user:u1`
- **WHEN** `u1` calls `GET /admin/users`
- **THEN** the response status is 200
- **AND** when `u1` calls `GET /admin/audit-log`, the response status is 200

### Requirement: Greenfield removal of the RBAC schema in a single migration

A single Alembic revision SHALL drop the `roles`, `permissions`, `role_permissions`, and `user_roles` tables and create the `relationships` table. The downgrade SHALL recreate empty RBAC tables and drop `relationships`. Data preservation across the upgrade SHALL NOT be required.

#### Scenario: Upgrade succeeds on an RBAC-shaped database

- **GIVEN** a database whose schema matches the prior RBAC migration
- **WHEN** `alembic upgrade head` runs
- **THEN** tables `roles`, `permissions`, `role_permissions`, `user_roles` no longer exist
- **AND** table `relationships` exists with the documented columns and indexes

#### Scenario: Migration round-trip succeeds

- **GIVEN** a database at the new head revision
- **WHEN** `alembic downgrade -1` runs and then `alembic upgrade head` runs
- **THEN** the schema after the round-trip is byte-equivalent to the schema before

### Requirement: SpiceDB adapter is a structural placeholder

The `SpiceDBAuthorizationAdapter` SHALL implement `AuthorizationPort` with the same five methods. Each method SHALL raise `NotImplementedError`. The adapter SHALL ship a README documenting which SpiceDB API maps to each port method and providing a `.zed` schema for the kanban and system resources. The adapter SHALL be excluded from coverage with `# pragma: no cover`.

#### Scenario: Stub raises with a helpful message

- **WHEN** any method on `SpiceDBAuthorizationAdapter` is called
- **THEN** the call raises `NotImplementedError`
- **AND** the message points to the adapter's README

#### Scenario: README documents the API and schema mapping

- **WHEN** the file `adapters/outbound/authorization/spicedb/README.md` is read
- **THEN** it lists the SpiceDB API call corresponding to each port method (`CheckPermission` → `check`, `LookupResources` → `lookup_resources`, `LookupSubjects` → `lookup_subjects`, `WriteRelationships` → `write_relationships`, `DeleteRelationships` → `delete_relationships`)
- **AND** it includes a `.zed` schema covering the `kanban` and `system` resource types

### Requirement: Authorization config is registered programmatically per feature

The system SHALL expose an ``AuthorizationRegistry`` whose ``register_resource_type`` and ``register_parent`` methods are the only mechanism by which a feature contributes resource types, actions, and parent-walk callables to the authorization engine. The registry SHALL refuse duplicate registrations, SHALL raise after ``seal()`` is called, and SHALL be the single source of truth read by the SQLModel adapter and any future adapter (SpiceDB, OpenFGA).

#### Scenario: A feature registers a leaf resource type

- **WHEN** a feature calls ``registry.register_resource_type("kanban", actions={...}, hierarchy={...})`` during composition
- **THEN** subsequent ``registry.relations_for("kanban", action)`` and ``registry.expand_relations("kanban", relations)`` calls return the registered values
- **AND** ``registry.has_stored_relations("kanban")`` returns ``True``

#### Scenario: A feature registers an inherited resource type

- **WHEN** a feature calls ``registry.register_parent("column", parent_of=lookup_fn, inherits_from="kanban")``
- **THEN** ``registry.parent_of("column", column_id)`` returns whatever ``lookup_fn`` returns
- **AND** ``registry.relations_for("column", "read")`` returns the kanban action map (inherited)
- **AND** ``registry.has_stored_relations("column")`` returns ``False``

#### Scenario: Duplicate registration is rejected

- **WHEN** a resource type is registered twice
- **THEN** the second call raises an explicit ``ValueError`` with both call sites' resource type in the message

#### Scenario: The registry is sealed after composition

- **WHEN** ``registry.seal()`` has been called
- **THEN** any subsequent ``register_resource_type`` or ``register_parent`` call raises a ``RuntimeError``
- **AND** read methods continue to work normally

### Requirement: Auth pre-registers only the system resource type

The auth feature SHALL register the ``system`` resource type with actions ``manage_users`` and ``read_audit`` (both requiring the ``admin`` relation) at container construction. Auth SHALL NOT register any other resource type. The kanban vocabulary (``kanban``, ``column``, ``card``) SHALL be registered exclusively from the kanban feature's composition wiring.

#### Scenario: Auth registers system without referencing kanban

- **WHEN** ``build_auth_container(...)`` returns
- **THEN** ``registry.has_stored_relations("system")`` returns ``True``
- **AND** ``registry.has_stored_relations("kanban")`` returns ``False``
- **AND** no source file under ``src/features/auth/application/authorization/`` contains the strings ``"kanban"``, ``"column"``, or ``"card"`` as resource-type identifiers

#### Scenario: Kanban registers its types from its own composition

- **WHEN** ``build_kanban_container(authorization=auth.authorization, registry=auth.registry, ...)`` returns
- **THEN** ``registry.has_stored_relations("kanban")`` returns ``True``
- **AND** ``registry.parent_of("card", "any-id")`` and ``registry.parent_of("column", "any-id")`` are callable

### Requirement: The engine resolves checks via the registry

``SQLModelAuthorizationAdapter.check`` SHALL walk parents through ``registry.parent_of`` until it lands on a resource type whose ``has_stored_relations`` is ``True``, then evaluate the check against the parent type's hierarchy using the originally requested action's relation set. ``check`` SHALL NOT contain branches that test for specific resource type names; the only knowledge the adapter has about resource types comes from the registry.

#### Scenario: A card check walks two levels to the board

- **GIVEN** kanban has registered ``card → column → kanban``
- **AND** a tuple ``kanban:{board_id}#owner@user:{user_id}`` exists
- **WHEN** ``check(user_id, "delete", "card", card_id)`` runs
- **THEN** the registry resolves the parent chain to ``("kanban", board_id)``
- **AND** the result is ``True``

#### Scenario: A check on a missing parent returns False

- **WHEN** ``check`` walks parents and any link returns ``None``
- **THEN** the result is ``False``
- **AND** no exception is raised

#### Scenario: A check on an unregistered resource type raises

- **WHEN** ``check(user_id, action, resource_type, resource_id)`` runs and ``resource_type`` was never registered
- **THEN** the call raises ``UnknownActionError``
- **AND** the platform's HTTP error mapping returns ``500`` (not 403) so the bug surfaces in integration testing
