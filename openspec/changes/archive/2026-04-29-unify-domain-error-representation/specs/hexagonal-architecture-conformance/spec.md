## ADDED Requirements

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
