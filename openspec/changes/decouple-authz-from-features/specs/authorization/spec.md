## ADDED Requirements

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
