# hexagonal-architecture-conformance Specification

## Purpose
TBD - created by archiving change unify-domain-error-representation. Update Purpose after archive.
## Requirements
### Requirement: Single canonical form for domain failures

Every kanban domain failure SHALL be represented exclusively by the
`KanbanError` enum carried inside a `Result[T, KanbanError]`. The codebase
SHALL NOT contain a parallel exception hierarchy (e.g. `KanbanDomainError`
and its subclasses) that encodes the same failure cases.

#### Scenario: domain methods return Result for invariant failures
- **WHEN** a domain method on `Board`, `Column`, or `Card` detects an
  invariant violation
- **THEN** it returns `Err(KanbanError.<CASE>)` instead of raising a
  domain exception

#### Scenario: no domain exception hierarchy
- **WHEN** a contributor inspects `src/domain/kanban/`
- **THEN** there is no `exceptions.py` declaring `KanbanDomainError` or
  its subclasses (`BoardNotFoundError`, `ColumnNotFoundError`,
  `CardNotFoundError`, `InvalidCardMoveError`)

#### Scenario: application has a single translation function
- **WHEN** application code maps a domain failure into `ApplicationError`
- **THEN** it calls `from_domain_error(KanbanError)` and there is no
  `from_domain_exception` function in the codebase

### Requirement: Aggregate-specific domain errors live under their aggregate package

The `src/domain/shared/` package SHALL NOT contain modules, classes, or
constants whose names or members are aggregate-specific. Aggregate-specific
error types SHALL live under `src/domain/<aggregate>/`.

#### Scenario: KanbanError lives in src/domain/kanban
- **WHEN** a contributor looks for `KanbanError`
- **THEN** it is defined in `src/domain/kanban/errors.py`, not in
  `src/domain/shared/errors.py`

#### Scenario: domain.shared exports only cross-aggregate symbols
- **WHEN** `src/domain/shared/__init__.py` is inspected
- **THEN** every re-exported symbol is generic (e.g. `Result`, `Ok`, `Err`)
  and no symbol contains an aggregate stem such as `Kanban`

### Requirement: Single Result type reused across domain and application

The codebase SHALL declare exactly one `Result` family. Application code
SHALL reuse `Ok`, `Err`, and `Result` from `src.domain.shared.result`
rather than defining parallel types.

#### Scenario: no AppOk/AppErr/AppResult clones
- **WHEN** a contributor searches the codebase for `AppOk`, `AppErr`, or
  `AppResult`
- **THEN** none of those symbols are defined or imported

#### Scenario: application handlers use domain Result types
- **WHEN** an application command or query handler returns a fallible
  outcome
- **THEN** the return type is `Result[T, ApplicationError]` using the
  `Result`, `Ok`, `Err` symbols from `src.domain.shared.result`

### Requirement: Application shared package is aggregate-neutral

The `src/application/shared/` package SHALL NOT contain modules,
classes, or imports that are aggregate-specific. Aggregate-specific
application errors and translations SHALL live under
`src/application/<aggregate>/`.

#### Scenario: ApplicationError lives in a kanban-namespaced module
- **WHEN** a contributor looks for `ApplicationError`,
  `from_domain_error`, or the `_ERROR_MAP` mapping table
- **THEN** they are defined under `src/application/kanban/errors.py`
  (or another aggregate-namespaced module), not under
  `src/application/shared/`

#### Scenario: application.shared imports no aggregate module
- **WHEN** any module under `src/application/shared/` declares an import
- **THEN** the import does not target `src.domain.<aggregate>.*` for any
  aggregate package present under `src/domain/`; imports of
  `src.domain.shared.*` and standard-library / third-party modules are
  allowed

### Requirement: Architecture tests enforce shared-package neutrality and Result uniqueness

The `tests/architecture/` suite SHALL include tests, marked
`@pytest.mark.architecture`, that fail if any of the following invariants
are violated:

- A class, module, or assignment under `src/domain/shared/` contains the
  stem of an aggregate package present under `src/domain/`.
- A module under `src/application/shared/` imports any module under
  `src/domain/<aggregate>/` other than `src/domain/shared/`.
- Any module in `src/application/` declares a class or alias named
  `AppOk`, `AppErr`, or `AppResult`.

#### Scenario: shared-package contamination fails the suite
- **WHEN** a contributor moves a kanban-specific symbol back into
  `src/domain/shared/` or `src/application/shared/`
- **THEN** running `uv run pytest tests/architecture -m architecture`
  exits non-zero with a failure that names the offending module

#### Scenario: AppResult reintroduction fails the suite
- **WHEN** a contributor reintroduces `AppOk`, `AppErr`, or `AppResult`
  anywhere under `src/application/`
- **THEN** the architecture test for Result uniqueness fails and names
  the offending module

### Requirement: Use cases are single orchestration units

Every application use case under `src/application/use_cases/` SHALL be
declared as a class whose `execute` method contains the orchestration
body. The class SHALL NOT delegate the entire body of `execute` to a
free function defined in another module.

#### Scenario: execute body contains the orchestration
- **WHEN** a contributor opens any `src/application/use_cases/*/<verb>.py`
  file
- **THEN** the class's `execute` method contains the actual repository
  calls, domain interactions, mapping, and `Result` construction —
  not a single line forwarding all arguments to an external function

#### Scenario: no handle_* free functions in commands or queries packages
- **WHEN** a contributor inspects `src/application/commands/` and
  `src/application/queries/`
- **THEN** no module defines a function whose name starts with
  `handle_`. The packages contain only command and query DTO classes
  (and helpers strictly local to those DTOs)

#### Scenario: API dependencies still construct use case classes
- **WHEN** `src/api/dependencies/use_cases.py` resolves a use case for a
  FastAPI route
- **THEN** it instantiates a `<Verb>UseCase` class with the required
  ports and returns the instance — the call surface for routes
  remains `use_case.execute(command_or_query)`

### Requirement: Architecture test forbids reintroducing the pass-through shape

The `tests/architecture/` suite SHALL include a test, marked
`@pytest.mark.architecture`, that fails if either of the following
holds:

- A class declared under `src/application/use_cases/` whose name ends
  in `UseCase` has an `execute` method whose entire body is a single
  `return <call>` statement where `<call>` targets a function whose
  name starts with `handle_` defined in another module.
- A module under `src/application/commands/` or
  `src/application/queries/` defines a function whose name starts with
  `handle_`.

#### Scenario: pass-through use case fails the suite
- **WHEN** a contributor reintroduces a `handle_*` function and a
  use case class whose `execute` body is `return handle_<verb>(...)`
- **THEN** running `uv run pytest tests/architecture -m architecture`
  exits non-zero with a failure that names the offending class and
  module

#### Scenario: free handler function in commands fails the suite
- **WHEN** a contributor adds `def handle_create_card(...)` to a module
  under `src/application/commands/`
- **THEN** the architecture test fails and names the offending module

#### Scenario: legitimate orchestration passes the suite
- **WHEN** a use case class's `execute` method calls multiple methods
  on injected ports, performs domain interactions, and returns a
  `Result`
- **THEN** the test passes regardless of the number of statements
  inside `execute`

### Requirement: DI module exposes a single canonical name per concept

The DI package `src/infrastructure/config/di/` SHALL declare exactly one
public name for each concept it exposes. It SHALL NOT carry
"backward-compatible" aliases when there are no production consumers
that would break by removal. Each concept's canonical name SHALL be the
one whose body contains the actual implementation; thin wrappers
created solely to preserve a legacy import path SHALL be removed.

#### Scenario: no `repository` alias on the container
- **WHEN** a contributor inspects `ConfiguredAppContainer`
- **THEN** there is no `repository` property; consumers access
  `container.repositories.kanban` directly

#### Scenario: no `create_repository_for_settings` helper
- **WHEN** a contributor inspects
  `src/infrastructure/config/di/composition.py`
- **THEN** there is no `create_repository_for_settings` function;
  consumers call `create_kanban_repository_for_settings(settings)`
  directly

#### Scenario: DI `__all__` lists each name once
- **WHEN** `src/infrastructure/config/di/__init__.py` is inspected
- **THEN** every entry in `__all__` is the canonical name of its
  concept; no entry is documented as a wrapper or alias

### Requirement: Architecture test forbids backward-compatible aliases without consumers

The `tests/architecture/` suite SHALL include a test, marked
`@pytest.mark.architecture`, that fails if any class, function, method,
or property declared under `src/infrastructure/config/di/` has a
docstring containing the phrase "backward-compatible" (case-insensitive)
unless every consumer of that symbol can be located under `src/`
(production code, not tests only).

#### Scenario: alias documented as backward-compatible without production consumers fails the suite
- **WHEN** a contributor adds a property whose docstring says
  "backward-compatible" and the only consumers live under `tests/`
- **THEN** running `uv run pytest tests/architecture -m architecture`
  exits non-zero with a failure that names the offending symbol

#### Scenario: legitimate compatibility shim with production consumers passes
- **WHEN** a future change introduces a deprecated alias that production
  code under `src/` still calls, and the docstring is updated to point
  at the canonical replacement
- **THEN** the architecture test passes (the rule fails only when there
  are zero production consumers)

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
