## REMOVED Requirements

### Requirement: SpiceDB adapter is a structural placeholder

**Reason:** This requirement is wholly about the
`SpiceDBAuthorizationAdapter` stub and its README — the package
`src/features/authorization/adapters/outbound/spicedb/`
(`__init__.py`, `adapter.py`, `README.md`). ROADMAP ETAPA I step 6
deletes that package: it was a never-wired structural placeholder
(constructed by nothing, every method raised `NotImplementedError`) and
the ROADMAP decision is to remove non-AWS production-shaped adapters.
The "swap a real backend in later" capability is provided by the
surviving `AuthorizationPort` Protocol itself, not by this stub. With the
package gone, the `# pragma: no cover` stub, its `NotImplementedError`
message, and its `.zed`-schema / SpiceDB-API-mapping README no longer
exist; this requirement is removed rather than left asserting deleted
code. No replacement requirement is introduced — a real ReBAC backend
adapter and its conformance contract are a future roadmap concern, not
ROADMAP ETAPA I cleanup.

## MODIFIED Requirements

### Requirement: AuthorizationPort defines the application-side authorization contract

The system SHALL expose an ``AuthorizationPort`` Protocol — now in ``src/features/authorization/application/ports/`` — that the application layer calls for every authorization decision. The port SHALL define exactly five methods: ``check``, ``lookup_resources``, ``lookup_subjects``, ``write_relationships``, and ``delete_relationships``. Adapters SHALL implement this port, and the application layer SHALL never depend on a concrete adapter type. The port and its adapters SHALL live entirely inside the authorization feature; auth and kanban depend on the port, never on the implementation.

#### Scenario: Application code depends only on the port

- **WHEN** any use case under ``src/features/authorization/application/``, ``src/features/auth/application/``, or ``src/features/kanban/application/`` performs an authorization decision
- **THEN** the use case takes an ``AuthorizationPort`` as a constructor dependency
- **AND** no module under ``application/`` of any feature imports from ``adapters/outbound/`` of any feature

#### Scenario: The SQLModel adapter implements the port

- **WHEN** the codebase is loaded
- **THEN** ``SQLModelAuthorizationAdapter`` (under ``src/features/authorization/adapters/outbound/sqlmodel/``) implements ``AuthorizationPort``
- **AND** it is the only shipped ``AuthorizationPort`` implementation; the port remains the single swap boundary so a future ReBAC backend can be introduced as one new adapter without an application-layer rewrite

### Requirement: Authorization is a self-contained feature slice

The system SHALL host authorization concerns in a dedicated feature slice at ``src/features/authorization/``. The slice SHALL contain the ``AuthorizationPort``, the ``AuthorizationRegistry``, the SQLModel adapter, and the ``BootstrapSystemAdmin`` use case. The slice SHALL NOT import from any other feature.

#### Scenario: Authorization owns the engine code

- **WHEN** the codebase is loaded
- **THEN** ``src/features/authorization/`` contains the engine, registry, ports, and bootstrap
- **AND** ``src/features/auth/`` does NOT contain any of those

#### Scenario: Authorization does not import from auth or kanban

- **WHEN** the codebase is loaded
- **THEN** no module under ``src/features/authorization/`` imports from ``src/features/auth/`` or ``src/features/kanban/``
- **AND** the import-linter contract "Authorization does not import from auth" passes

### Requirement: Authorization config is registered programmatically per feature

The system SHALL expose an ``AuthorizationRegistry`` whose ``register_resource_type`` and ``register_parent`` methods are the only mechanism by which a feature contributes resource types, actions, and parent-walk callables to the authorization engine. The registry SHALL refuse duplicate registrations, SHALL raise after ``seal()`` is called, and SHALL be the single source of truth read by the SQLModel adapter and any future ``AuthorizationPort`` adapter.

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
