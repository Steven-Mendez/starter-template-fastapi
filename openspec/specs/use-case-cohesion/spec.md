# use-case-cohesion Specification

## Purpose
TBD - created by archiving change hex-conformance-finalization. Update Purpose after archive.
## Requirements
### Requirement: One Use Case Per Business Intent
The application layer MUST express each business intent as a single dedicated use-case class. Generic aggregator classes that hold multiple unrelated handlers (for example, a class with `handle_create_board`, `handle_patch_board`, and `handle_delete_board` methods on one object) are forbidden.

#### Scenario: New command introduces a dedicated use case
- **WHEN** a new command-side intent is added to the application layer
- **THEN** it is implemented as a class whose name ends in `UseCase`, lives in its own file under `src/application/use_cases/<aggregate>/<verb>_<noun>.py`, and exposes exactly one public method named `execute`

#### Scenario: New query introduces a dedicated use case
- **WHEN** a new query-side intent is added to the application layer
- **THEN** it is implemented as a class whose name ends in `UseCase`, lives in its own file under `src/application/use_cases/<aggregate>/<verb>_<noun>.py`, and exposes exactly one public method named `execute`

#### Scenario: Aggregator service object is rejected
- **WHEN** a class in `src/application/` declares two or more public methods that orchestrate distinct business intents (for example, both creation and deletion of an aggregate)
- **THEN** the conformance suite fails citing the `use-case-cohesion` capability

### Requirement: Use-Case Constructor Depends Only on Ports
A use-case class constructor MUST receive only port abstractions (`*Port`) or other use-case-level collaborators that are themselves typed as protocols. Concrete adapter classes, FastAPI dependency markers, ORM sessions, and configuration objects MUST NOT appear in use-case constructor signatures.

#### Scenario: Use case constructor takes a port
- **WHEN** `CreateBoardUseCase` requires persistence access
- **THEN** its constructor parameter is typed as `UnitOfWorkPort`, not as a concrete `SqlModelUnitOfWork`

#### Scenario: Concrete adapter type in use case constructor is rejected
- **WHEN** any class under `src/application/use_cases/` declares a constructor parameter whose type annotation resolves to a class defined under `src/infrastructure/`
- **THEN** the conformance suite fails

### Requirement: Use Case Names Communicate Intent
Use-case class names MUST be in `VerbNounUseCase` form, where verb and noun describe the business intent and not the technology or CRUD layer.

#### Scenario: Intent-revealing name accepted
- **WHEN** a class is named `PlaceOrderUseCase`, `CancelOrderUseCase`, `PatchCardUseCase`, or `CheckReadinessUseCase`
- **THEN** the conformance suite accepts the name

#### Scenario: Generic-service name rejected
- **WHEN** a class is named `OrderService`, `CardManager`, `BoardHandler`, or `KanbanCommandHandlers`
- **THEN** the conformance suite fails citing the `Use-case names should communicate intent` rule

### Requirement: Per-Route Dependency Injection
Inbound FastAPI routes MUST receive only the specific use case(s) they invoke through `Depends(...)` factories. Routes MUST NOT depend on aggregator handler containers that expose multiple unrelated use cases.

#### Scenario: Route depends on its specific use case
- **WHEN** the `POST /boards` route is implemented
- **THEN** it declares a dependency typed as `CreateBoardUseCase` provided via `Depends(get_create_board_use_case)` and on no other use case

#### Scenario: Route depends on aggregator is rejected
- **WHEN** any route function declares a dependency whose type exposes more than one use case
- **THEN** the conformance suite fails

### Requirement: Per-Use-Case DI Factories Live at the API Edge
The composition of a use case with its concrete adapters MUST happen inside `src/api/dependencies/` (or `src/infrastructure/config/di/`) factory functions, one factory function per use case. Use cases themselves MUST NOT import from `fastapi`.

#### Scenario: Factory function exists for each use case
- **WHEN** a use-case class `XUseCase` is defined under `src/application/use_cases/`
- **THEN** a factory function `get_<x>_use_case` exists at the API edge that returns an instance of `XUseCase` with concrete adapter wiring

#### Scenario: Use case imports FastAPI is rejected
- **WHEN** any module under `src/application/use_cases/` imports from `fastapi`
- **THEN** the conformance suite fails

### Requirement: Use Cases Return AppResult or Raw Domain Read-Models
Use-case `execute` methods MUST return either `AppResult[T, ApplicationError]` for fallible business intents or a domain read-model contract for read-only queries. They MUST NOT return FastAPI response objects, ORM rows, or raise transport exceptions.

#### Scenario: Use case returns AppResult
- **WHEN** `CreateBoardUseCase.execute` succeeds
- **THEN** it returns `AppOk(AppBoardSummary(...))` and never a `JSONResponse` or `HTTPException`

#### Scenario: Use case raises HTTPException is rejected
- **WHEN** any module under `src/application/use_cases/` references `fastapi.HTTPException` or `starlette.exceptions.HTTPException`
- **THEN** the conformance suite fails

### Requirement: Removal of Mega Input Ports
The historical aggregator types `KanbanCommandInputPort`, `KanbanQueryInputPort`, `KanbanCommandHandlers`, and `KanbanQueryHandlers` MUST be removed from the codebase. Any reintroduction of an aggregator port that bundles unrelated business intents into a single Protocol is non-compliant.

#### Scenario: Aggregator port reintroduced
- **WHEN** a `Protocol` class is added that declares two or more methods whose names follow the pattern `handle_<verb>_<noun>` for distinct nouns
- **THEN** the conformance suite fails

#### Scenario: Legacy symbols absent
- **WHEN** the conformance suite runs
- **THEN** the symbols `KanbanCommandInputPort`, `KanbanQueryInputPort`, `KanbanCommandHandlers`, and `KanbanQueryHandlers` are not importable from `src.application` or any submodule
