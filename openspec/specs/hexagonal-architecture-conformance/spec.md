# hexagonal-architecture-conformance Specification

## Purpose
TBD - created by archiving change hex-conformance-finalization. Update Purpose after archive.
## Requirements
### Requirement: Automated Conformance Suite is the Source of Truth
The system MUST treat the architecture conformance test suite as the single source of truth for hexagonal-architecture compliance with this capability. The requirements declared in this specification MUST be encoded as machine-verifiable tests under `tests/architecture/`, and a passing suite MUST imply conformance with this capability.

#### Scenario: Conformance suite gate present
- **WHEN** the project's automated checks (`make check`, `pre-commit`, or CI) run
- **THEN** the suite under `tests/architecture/` executes and a non-zero exit code blocks the build

### Requirement: Domain Layer Purity Enforced Mechanically
The domain layer MUST NOT depend on web frameworks, ORMs, transport schemas, configuration loaders, or third-party I/O SDKs, and this constraint MUST be enforced by automated import checks rather than human review.

#### Scenario: Forbidden import in domain fails the build
- **WHEN** any module under `src/domain/` imports from `fastapi`, `starlette`, `sqlmodel`, `sqlalchemy`, `httpx`, `pydantic`, `pydantic_settings`, `psycopg`, `alembic`, `src.application`, `src.api`, or `src.infrastructure`
- **THEN** the import-graph contract or the architecture suite fails with a diagnostic naming the offending module and import

#### Scenario: Domain entity may use only stdlib and intra-domain imports
- **WHEN** a new entity, value object, or domain service file is added under `src/domain/`
- **THEN** the conformance suite validates that its imports resolve only to the Python standard library or to other modules under `src/domain/`

### Requirement: Application Layer Free of Transport and Persistence Coupling
The application layer MUST NOT import FastAPI dependency markers, FastAPI request/response types, ORM clients, HTTP clients, or any module under `src.infrastructure` or `src.api`.

#### Scenario: FastAPI Depends in application layer fails
- **WHEN** any module under `src/application/` imports `fastapi.Depends`, `fastapi.Request`, `fastapi.Response`, or `fastapi.HTTPException`
- **THEN** the conformance suite fails with a message identifying the file and the forbidden symbol

#### Scenario: Concrete persistence in application layer fails
- **WHEN** any module under `src/application/` imports from `sqlmodel`, `sqlalchemy`, `psycopg`, `httpx`, `boto3`, `redis`, `kafka`, or `src.infrastructure`
- **THEN** the conformance suite fails with a message identifying the file and the forbidden module

### Requirement: Pydantic Confined to the API Adapter
Pydantic models (`pydantic.BaseModel`, `pydantic.RootModel`, `pydantic.Field`-using classes) MUST be defined and consumed only inside `src/api/`.

#### Scenario: Pydantic model defined outside API
- **WHEN** a module outside `src/api/` defines a class inheriting from `pydantic.BaseModel`
- **THEN** the conformance suite fails

#### Scenario: API schema imports stay inbound
- **WHEN** any module under `src/api/schemas/` is imported from outside `src/api/`
- **THEN** the conformance suite fails

### Requirement: Anti-Pattern Guards Applied to Application Classes
The conformance suite MUST flag application-layer anti-patterns that contradict the use-case-cohesion capability. At minimum the suite MUST detect (a) generic service objects that aggregate multiple unrelated business intents on a single class, and (b) anemic pass-through use cases that delegate to a single repository method without invoking any domain object.

#### Scenario: Mega service detected
- **WHEN** a class under `src/application/` declares more than one public method that is part of an inbound port and is not a use case
- **THEN** the conformance suite fails citing the `use-case-cohesion` capability

#### Scenario: Anemic pass-through use case detected
- **WHEN** a class ending in `UseCase` under `src/application/use_cases/` has an `execute` method whose body delegates to a single repository method without invoking any domain object
- **THEN** the conformance suite emits a warning entry naming the file (the warning category SHALL be reviewable in CI logs)

### Requirement: Mapper and Read-Model Boundary Enforced
Persistence mappers MUST NOT import application contracts, and outbound query adapters MUST return domain or read-model types declared in `src/domain/` or `src/application/contracts/` only.

#### Scenario: Persistence mapper imports application contract
- **WHEN** any module under `src/infrastructure/adapters/outbound/persistence/` imports from `src/application/contracts/`
- **THEN** the conformance suite fails

#### Scenario: Outbound adapter returns ORM type
- **WHEN** the public return type annotation of any function in `src/infrastructure/adapters/outbound/` is an ORM model class (a subclass of `sqlmodel.SQLModel` or `sqlalchemy.orm.DeclarativeBase`)
- **THEN** the conformance suite fails

### Requirement: Routes Stay Thin
FastAPI route handler bodies MUST be limited to: parsing input, mapping to a command/query, invoking exactly one use case, and mapping the result. Business orchestration in routes is forbidden.

#### Scenario: Route invokes more than one use case
- **WHEN** a function decorated with a FastAPI router method (`@*.get`, `@*.post`, etc.) inside `src/api/routers/` calls more than one object whose class name ends in `UseCase`
- **THEN** the conformance suite fails

#### Scenario: Route imports infrastructure directly
- **WHEN** any module under `src/api/routers/` imports from `src/infrastructure/`
- **THEN** the conformance suite fails

### Requirement: Conformance Diagnostics Reference the Spec Capability
Each architecture test failure MUST surface a diagnostic that names the spec capability whose requirement is being enforced so that developers and agents can locate the normative rule directly in `openspec/specs/<capability>/spec.md` without consulting external material.

#### Scenario: Failure message cites the spec capability
- **WHEN** the conformance suite fails any assertion that enforces this capability
- **THEN** the assertion message contains the substring `hexagonal-architecture-conformance:` followed by a short human-readable description of the violated rule

#### Scenario: Failure message cites the relevant capability when not this one
- **WHEN** the conformance suite fails an assertion that enforces a different hex-related capability (e.g., `use-case-cohesion`, `adapter-topology-conventions`, `error-boundary-and-translation`)
- **THEN** the assertion message contains the substring `<capability-name>:` matching the kebab-case capability id under `openspec/specs/`
