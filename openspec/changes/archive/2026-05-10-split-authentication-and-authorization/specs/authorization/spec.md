## MODIFIED Requirements

### Requirement: AuthorizationPort defines the application-side authorization contract

The system SHALL expose an ``AuthorizationPort`` Protocol — now in ``src/features/authorization/application/ports/`` — that the application layer calls for every authorization decision. The port SHALL define exactly five methods: ``check``, ``lookup_resources``, ``lookup_subjects``, ``write_relationships``, and ``delete_relationships``. Adapters SHALL implement this port, and the application layer SHALL never depend on a concrete adapter type. The port and its adapters SHALL live entirely inside the authorization feature; auth and kanban depend on the port, never on the implementation.

#### Scenario: Application code depends only on the port

- **WHEN** any use case under ``src/features/authorization/application/``, ``src/features/auth/application/``, or ``src/features/kanban/application/`` performs an authorization decision
- **THEN** the use case takes an ``AuthorizationPort`` as a constructor dependency
- **AND** no module under ``application/`` of any feature imports from ``adapters/outbound/`` of any feature

#### Scenario: Two adapters implement the port

- **WHEN** the codebase is loaded
- **THEN** ``SQLModelAuthorizationAdapter`` (under ``src/features/authorization/adapters/outbound/sqlmodel/``) implements ``AuthorizationPort``
- **AND** ``SpiceDBAuthorizationAdapter`` (under ``src/features/authorization/adapters/outbound/spicedb/``) implements ``AuthorizationPort``
- **AND** the SpiceDB adapter raises ``NotImplementedError`` from each method with a message pointing to its README

## ADDED Requirements

### Requirement: Authorization is a self-contained feature slice

The system SHALL host authorization concerns in a dedicated feature slice at ``src/features/authorization/``. The slice SHALL contain the ``AuthorizationPort``, the ``AuthorizationRegistry``, the SQLModel adapter, the SpiceDB stub, and the ``BootstrapSystemAdmin`` use case. The slice SHALL NOT import from any other feature.

#### Scenario: Authorization owns the engine code

- **WHEN** the codebase is loaded
- **THEN** ``src/features/authorization/`` contains the engine, registry, ports, and bootstrap
- **AND** ``src/features/auth/`` does NOT contain any of those

#### Scenario: Authorization does not import from auth or kanban

- **WHEN** the codebase is loaded
- **THEN** no module under ``src/features/authorization/`` imports from ``src/features/auth/`` or ``src/features/kanban/``
- **AND** the import-linter contract "Authorization does not import from auth" passes

### Requirement: Cache invalidation flows through UserAuthzVersionPort

Authorization SHALL bump ``User.authz_version`` after any ``write_relationships`` or ``delete_relationships`` call that touches a ``user`` subject by calling ``UserAuthzVersionPort.bump(user_id)``. The port is defined in ``src/features/authorization/application/ports/outbound/`` and implemented by an adapter in the auth feature.

#### Scenario: A relationship write triggers a port call per affected user subject

- **GIVEN** a relationships write batch with two distinct user subjects ``u1`` and ``u2``
- **WHEN** ``write_relationships(...)`` returns
- **THEN** ``UserAuthzVersionPort.bump`` was called once with ``u1`` and once with ``u2``

#### Scenario: Non-user subjects do not trigger the port

- **WHEN** a write contains only ``service``-typed subjects
- **THEN** ``UserAuthzVersionPort.bump`` is not called

### Requirement: Bootstrap depends on UserRegistrarPort

The ``BootstrapSystemAdmin`` use case SHALL live in ``src/features/authorization/application/use_cases/`` and SHALL depend on ``UserRegistrarPort`` (defined in authorization's outbound ports). It SHALL NOT import ``RegisterUser`` or any other auth-feature symbol.

#### Scenario: Bootstrap composes user registration through the port

- **WHEN** ``BootstrapSystemAdmin.execute(email, password)`` runs
- **THEN** the use case calls ``UserRegistrarPort.register_or_lookup(email=..., password=...)``
- **AND** the returned ``user_id`` is used to write the system-admin tuple
- **AND** the use case writes one audit event of type ``authz.bootstrap_admin_assigned`` via the ``AuditPort``

### Requirement: The relationships table is owned by the platform layer

The ``RelationshipTable`` SQLModel definition SHALL live in ``src/platform/persistence/sqlmodel/authorization/models.py``. The migration history for that table SHALL also be platform-owned going forward (Alembic operates on a single metadata; the location of the SQLModel class is what changes).

#### Scenario: The platform module declares the table

- **WHEN** the codebase is loaded
- **THEN** ``RelationshipTable`` is importable from ``src.platform.persistence.sqlmodel.authorization.models``
- **AND** it is NOT importable from ``src.features.auth.adapters.outbound.persistence.sqlmodel.models``
- **AND** it is NOT importable from ``src.features.authorization.adapters.outbound.sqlmodel.models``

#### Scenario: Migrations remain identical

- **WHEN** ``alembic upgrade head`` runs against a fresh database
- **THEN** the resulting schema matches the schema produced by the previous head exactly (column types, constraints, indexes)
- **AND** an empty migration anchors the move so future autogenerates start from the new module path

### Requirement: Layering is enforced by Import Linter

The ``pyproject.toml`` SHALL declare three forbidden contracts: ``auth → authorization`` is forbidden; ``authorization → auth`` is forbidden; ``kanban → auth`` is forbidden. ``make lint-arch`` SHALL fail if any contract breaks.

#### Scenario: The contracts are present and pass

- **WHEN** ``uv run lint-imports`` is invoked
- **THEN** the three new contracts are listed in the output
- **AND** all three are reported as KEPT
