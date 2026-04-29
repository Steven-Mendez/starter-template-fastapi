## Why

Domain and application currently encode the same four kanban failure cases
(`BOARD_NOT_FOUND`, `COLUMN_NOT_FOUND`, `CARD_NOT_FOUND`, `INVALID_CARD_MOVE`)
in two parallel forms, in two misnamed locations, with duplicated translation
plumbing in application:

- `src/domain/shared/errors.py` declares `KanbanError`, an enum with
  kanban-specific values living under `domain/shared/`. The skill's
  "Recommended Structure" reserves `domain/shared/` for cross-aggregate
  concepts (`money.py`, `email.py`) and places aggregate errors under
  `domain/<aggregate>/exceptions.py`.
- `src/domain/kanban/exceptions.py` declares the same four cases as a
  `KanbanDomainError` subclass hierarchy.
- Repositories return `Result[..., KanbanError]` (enum form) while domain
  methods (e.g. `Column.insert_card`) raise `KanbanDomainError` (exception
  form). A single use case (`src/application/commands/card/create.py`)
  consumes both paths.
- `src/application/shared/errors.py` is named "shared" but only knows kanban,
  importing every kanban-specific exception class and maintaining two parallel
  mapping tables (`_ERROR_MAP`, `_EXCEPTION_ERROR_MAP`) to translate either
  form into `ApplicationError`.
- `src/application/shared/result.py` clones `Ok/Err/Result` from
  `src/domain/shared/result.py` as `AppOk/AppErr/AppResult` with no added
  semantics, no helper functions, and no behavioural difference. Application
  is allowed to import from domain (the inward dependency rule of the skill,
  lines 51–56), so this duplication is dead surface.

The result is: same information stored twice in domain, same translation
written twice in application, and a `shared/` namespace that contains
non-shared code on both sides.

## What Changes

- Choose a single canonical form for kanban domain failures and remove the
  redundant form. The technical decision (Result-only vs exceptions-only) is
  argued in `design.md`.
- Move the surviving form into `src/domain/kanban/` (out of
  `src/domain/shared/`), so `domain/shared/` only retains genuinely
  cross-aggregate building blocks (`Result`, helpers).
- Collapse `src/application/shared/result.py` into the domain `Result` types.
  Delete `AppOk`, `AppErr`, `AppResult` and replace every application-side
  reference with `Ok`, `Err`, `Result` from `src.domain.shared.result`.
- Move `src/application/shared/errors.py` (which is kanban-specific) to a
  kanban-namespaced module under application, leaving `application/shared/`
  with only truly cross-cutting code (`ReadinessProbe`, generic helpers).
- Update every consumer (use cases, command handlers, query handlers,
  repository ports, repository adapters, query view, API error mapper,
  tests) to use the unified surface.
- Add (or extend) an architecture test that fails if `src/domain/shared/`
  contains aggregate-specific identifiers (e.g. modules whose names match a
  known aggregate suffix or that expose enums with aggregate-specific values).
- Add an architecture test that fails if `src.application.shared.*` imports
  any module under `src.domain.<aggregate>.*` other than `src.domain.shared`,
  preventing the "shared module that knows kanban" anti-pattern from
  resurfacing.

No HTTP API contract, database schema, or domain rule changes. The
`ApplicationError` enum values exposed to inbound adapters and the resulting
HTTP problem-details payloads remain identical.

## Capabilities

### New Capabilities
<!-- None. -->

### Modified Capabilities
- `hexagonal-architecture-conformance`: adds requirements that constrain
  where domain-error and application-error types live, forbid duplicate
  `Result` representations, and forbid kanban-specific code under
  `application/shared/`. The `align-project-skeleton-to-hex-skill` change
  (which introduces this capability) must land first; this change extends it.

## Impact

- Affected code:
  - `src/domain/shared/errors.py` (removed or emptied).
  - `src/domain/shared/__init__.py` (export list trimmed).
  - `src/domain/__init__.py` (export list trimmed).
  - `src/domain/kanban/errors.py` or `src/domain/kanban/exceptions.py`
    (consolidated home for kanban failures, depending on the design.md
    decision).
  - `src/application/shared/result.py` (removed).
  - `src/application/shared/__init__.py` (no longer re-exports
    `AppOk`/`AppErr`/`AppResult`).
  - `src/application/shared/errors.py` (moved to
    `src/application/kanban/errors.py` or equivalent).
  - Every use case / handler in `src/application/commands/` and
    `src/application/queries/` that imports `AppOk`/`AppErr`/`AppResult` or
    `from_domain_error`/`from_domain_exception`.
  - Repository ports: `src/application/ports/kanban_command_repository.py`,
    `src/application/ports/kanban_query_repository.py`,
    `src/application/ports/kanban_lookup_repository.py` — return-type imports.
  - Repository adapter:
    `src/infrastructure/adapters/outbound/persistence/sqlmodel/repository.py`
    — return types and raised/returned errors.
  - Query view:
    `src/infrastructure/adapters/outbound/query/kanban_query_repository_view.py`.
  - API error mapper: `src/api/routers/_errors.py` (unchanged in surface, but
    the import of `ApplicationError` may move).
  - Tests under `tests/unit/`, `tests/integration/`, and `tests/architecture/`
    that reference the removed types.
- Affected configuration: none. Import-linter contracts already cover the
  layer boundaries; new architecture tests are pure additions.
- No dependency changes.
- No HTTP / DB / domain behaviour changes — `tests/integration` and
  `tests/e2e` must remain green without modification.
- Depends on `align-project-skeleton-to-hex-skill` because that change
  introduces the `hexagonal-architecture-conformance` spec being modified
  here. Apply order: skeleton change first, then this change.
