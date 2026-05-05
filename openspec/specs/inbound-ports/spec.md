# inbound-ports Specification

## Purpose
TBD - created by archiving change refactor-to-feature-first. Update Purpose after archive.
## Requirements
### Requirement: Inbound port per use case

For every use case class in a feature, the feature MUST define a corresponding `Protocol` in `src/features/<F>/application/ports/inbound/<verb>_<noun>.py` whose name is `<UseCase>UseCasePort`. The Protocol MUST declare a single `execute(...)` method with the same input/output types as the use case.

#### Scenario: CreateBoard use case has an inbound port
- **WHEN** the migration is complete
- **THEN** `src/features/kanban/application/ports/inbound/create_board.py` exposes a `CreateBoardUseCasePort` Protocol with `execute(self, cmd: CreateBoardCommand) -> Result[AppBoardSummary, ApplicationError]`

#### Scenario: All Kanban use cases covered
- **WHEN** the migration is complete
- **THEN** every concrete class under `src/features/kanban/application/use_cases/` has a matching inbound Protocol in `application/ports/inbound/`

### Requirement: HTTP adapters depend on Protocols, not concrete classes

Inbound HTTP adapters (FastAPI dependency factories and route handlers) MUST type their use case parameters using the inbound Protocol, not the concrete use case class. The composition root binds the Protocol to a concrete implementation.

#### Scenario: Router parameter typed as Protocol
- **WHEN** `src/features/kanban/adapters/inbound/http/boards.py` declares its `create_board` handler dependency
- **THEN** the dependency type is `CreateBoardUseCasePort` (or a `TypeAlias` over it), not `CreateBoardUseCase`

#### Scenario: Composition binds Protocol
- **WHEN** the dependency provider for `CreateBoardUseCasePort` resolves
- **THEN** it returns an instance of `CreateBoardUseCase` constructed from platform and feature ports

### Requirement: Inbound port purity

Inbound Protocol modules MUST NOT import from `src/features/<F>/adapters/` or from any framework. They MAY import from `src/features/<F>/application/{commands,queries,contracts,errors}` and `src/platform/shared/`.

#### Scenario: Inbound ports remain framework-free
- **WHEN** `make lint-arch` runs
- **THEN** no inbound port module imports `fastapi`, `starlette`, `sqlmodel`, `sqlalchemy`, or `pydantic_settings`
