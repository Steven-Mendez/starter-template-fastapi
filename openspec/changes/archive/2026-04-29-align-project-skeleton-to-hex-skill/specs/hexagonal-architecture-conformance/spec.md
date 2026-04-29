## ADDED Requirements

### Requirement: FastAPI entrypoint location

The FastAPI application factory and module-level `app` instance SHALL live at
`src/main.py`. No FastAPI application module SHALL exist at the repository
root, and no tooling configuration (`pyproject.toml`, `Dockerfile`,
`docker-compose.yml`, `Makefile`, CI workflows, `README.md`) SHALL reference
`main:app` as the uvicorn target.

#### Scenario: src/main.py exposes the app
- **WHEN** a developer runs `uvicorn src.main:app`
- **THEN** the FastAPI application starts and serves the API router

#### Scenario: no top-level main module
- **WHEN** a contributor inspects the repository root
- **THEN** there is no `./main.py` file containing a FastAPI application

#### Scenario: tooling references the new path
- **WHEN** `Dockerfile`, `docker-compose.yml`, the `Makefile`, and CI workflows
  invoke uvicorn
- **THEN** every invocation targets `src.main:app`, not `main:app`

### Requirement: Configuration lives inside infrastructure

`AppSettings` (the `pydantic_settings.BaseSettings` subclass that loads
environment variables and `.env`) SHALL reside under `src/infrastructure/`.
No application or domain module SHALL import settings from `src.config.*`,
and the package `src/config/` SHALL not exist.

#### Scenario: settings module location
- **WHEN** a contributor looks for `AppSettings`
- **THEN** it is defined at `src/infrastructure/config/settings.py`

#### Scenario: no top-level src.config package
- **WHEN** a contributor lists `src/`
- **THEN** there is no `src/config/` directory

#### Scenario: import-linter contracts no longer special-case src.config
- **WHEN** the import-linter contracts in `pyproject.toml` are inspected
- **THEN** `"src.config"` is not present in any `forbidden_modules` list
  (settings are reachable only as `src.infrastructure.config.settings`,
  already covered by the existing `src.infrastructure` prohibitions for
  domain and application sources)

### Requirement: Application repository ports are segregated

The `src/application/ports/` package SHALL NOT declare a Protocol that
inherits from more than one other Protocol whose name ends in
`RepositoryPort`. Application code SHALL depend on the segregated
`KanbanCommandRepositoryPort`, `KanbanQueryRepositoryPort`, and
`KanbanLookupRepositoryPort` directly. Any composite repository type
required for infrastructure wiring SHALL live under `src/infrastructure/`.

#### Scenario: no aggregator port in application layer
- **WHEN** a contributor inspects `src/application/ports/`
- **THEN** there is no module declaring an aggregator such as
  `KanbanRepositoryPort` that combines command, query, and lookup
  repository protocols

#### Scenario: use cases depend on segregated ports only
- **WHEN** a use case or application handler types its dependencies
- **THEN** it references one of `KanbanCommandRepositoryPort`,
  `KanbanQueryRepositoryPort`, `KanbanLookupRepositoryPort`, or
  `UnitOfWorkPort` (which exposes `commands` and `lookup` already), and
  not an aggregator port

#### Scenario: infrastructure composite type lives in infrastructure
- **WHEN** the DI container needs a composite type that bundles repository
  capabilities with `ReadinessProbe` and `ClosableResource`
- **THEN** that type is declared under `src/infrastructure/` (for example,
  `ManagedKanbanRepositoryPort` in `src/infrastructure/config/di/composition.py`),
  not under `src/application/ports/`

### Requirement: Architecture test forbids future repository aggregators

The `tests/architecture/` suite SHALL include a test, marked
`@pytest.mark.architecture`, that fails if any Protocol declared under
`src.application.ports` inherits from more than one base whose name ends in
`RepositoryPort`.

#### Scenario: aggregator reintroduction fails the suite
- **WHEN** a contributor adds a Protocol in `src/application/ports/` that
  inherits from two or more `*RepositoryPort` Protocols
- **THEN** running `uv run pytest tests/architecture -m architecture` exits
  non-zero with a failure that names the offending class and module

#### Scenario: segregated ports remain valid
- **WHEN** the existing `KanbanCommandRepositoryPort`,
  `KanbanQueryRepositoryPort`, and `KanbanLookupRepositoryPort` Protocols
  are present
- **THEN** the architecture test passes
