## MODIFIED Requirements

### Requirement: Explicit Adapter Topology
The system MUST maintain explicit and separate module topology for inbound adapters and outbound adapters, and ALL outbound adapters (including persistence, clocks, identifier generators, query views, and external integrations) MUST live under a single `src/infrastructure/adapters/outbound/<concern>/` tree. Sibling outbound trees outside `src/infrastructure/adapters/outbound/` are forbidden.

#### Scenario: Inbound adapter placement is deterministic
- **WHEN** a new HTTP endpoint adapter is added
- **THEN** it is placed under the inbound adapter topology (`src/api/`) and does not contain outbound persistence logic

#### Scenario: Outbound adapter placement is deterministic
- **WHEN** a new persistence adapter is added
- **THEN** it is placed under `src/infrastructure/adapters/outbound/persistence/<technology>/` and does not import inbound transport modules

#### Scenario: Sibling outbound tree rejected
- **WHEN** a new module is added directly under `src/infrastructure/` that contains an adapter implementing an outbound port (for example, `src/infrastructure/persistence/`, `src/infrastructure/messaging/`, or `src/infrastructure/external/`) instead of being placed under `src/infrastructure/adapters/outbound/`
- **THEN** the architecture conformance suite fails citing this requirement

#### Scenario: Persistence module canonical location
- **WHEN** the SQLModel persistence adapter, unit of work, mappers, ORM models, and lifecycle helpers are accessed
- **THEN** they import from `src.infrastructure.adapters.outbound.persistence.sqlmodel.*` and `src.infrastructure.adapters.outbound.persistence.lifecycle`

### Requirement: Naming Convention Consistency
Adapter and boundary components MUST follow consistent naming conventions for intent clarity, and the conformance suite MUST verify naming.

#### Scenario: Port and adapter names communicate role
- **WHEN** a new boundary component is introduced
- **THEN** names follow defined conventions (`*Port` for ports; `*Repository`, `*UnitOfWork`, `*Adapter`, `*View`, `*Mapper`, `*Clock`, `*IdGenerator` for adapters; `*UseCase` for application use cases) and match module responsibility

#### Scenario: Naming violation detected by suite
- **WHEN** a class under `src/application/ports/` does not have a name ending in `Port`, or a class under `src/infrastructure/adapters/outbound/` does not have a name ending in one of `Repository`, `UnitOfWork`, `Adapter`, `View`, `Mapper`, `Clock`, or `IdGenerator`
- **THEN** the conformance suite fails citing this requirement
