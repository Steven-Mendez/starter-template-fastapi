# platform-shared-kernel Specification

## Purpose
TBD - created by archiving change refactor-to-feature-first. Update Purpose after archive.
## Requirements
### Requirement: Platform package scope

The `src/platform/` package MUST contain only cross-feature concerns: settings, app factory, error handlers, request middleware, persistence engine wiring, readiness, and a shared kernel of cross-feature value objects/ports/adapters. It MUST NOT contain any business logic specific to a single feature.

#### Scenario: Platform stays feature-agnostic
- **WHEN** a developer attempts to import `src.features.kanban.*` from any module under `src/platform/`
- **THEN** `make lint-arch` fails with a contract violation

### Requirement: Platform subpackages

The `src/platform/` package MUST expose at least: `config/` (settings), `api/` (app factory, error handlers, middleware, dependencies), `persistence/` (engine, lifecycle, readiness), `shared/` (Result, ClockPort, IdGeneratorPort and their default adapters).

#### Scenario: Required subpackages exist
- **WHEN** the refactor is complete
- **THEN** `src/platform/config/`, `src/platform/api/`, `src/platform/persistence/`, `src/platform/shared/` each exist and contain at least one Python module

### Requirement: Shared kernel content

`src/platform/shared/` MUST expose: a `Result[V, E]` algebraic type with `Ok` and `Err` constructors, a `ClockPort` Protocol, an `IdGeneratorPort` Protocol, and default adapters `SystemClock` and `UuidIdGenerator`.

#### Scenario: Use cases can depend on shared kernel
- **WHEN** a Kanban use case returns `Result[AppBoardSummary, ApplicationError]`
- **THEN** it imports `Result`, `Ok`, `Err` from `src.platform.shared.result`
- **AND** mypy strict mode passes on the import

### Requirement: Platform exposes a single platform container

The platform MUST provide a `build_platform(settings: AppSettings) -> PlatformContainer` factory that constructs the shared engine, clock, id generator, and readiness probe. Each feature's `register_<F>(app, platform)` consumes this container.

#### Scenario: Platform built once per app lifespan
- **WHEN** `create_app()` is called
- **THEN** `build_platform` is invoked exactly once during the lifespan startup
- **AND** the resulting container is shared across all registered features
