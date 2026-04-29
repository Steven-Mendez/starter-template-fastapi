## Why

The FastAPI hexagonal-architecture skill explicitly names "Anemic pass-through
use cases" as Anti-pattern 2 (`./.opencode/skills/fastapi-hexagonal-architecture/SKILL.md`,
lines 1077–1086). Every use case in the codebase matches that anti-pattern:
the class declares dependencies as fields and its single `execute` method
delegates 1:1 to a free function `handle_*`, with no orchestration, state, or
behaviour added by the class.

Concrete instances (10/10 use cases):

```11:17:src/application/use_cases/board/get_board.py
@dataclass(slots=True)
class GetBoardUseCase:
    query_repository: KanbanQueryRepositoryPort

    def execute(self, query: GetBoardQuery) -> AppResult[AppBoard, ApplicationError]:
        return handle_get_board(repository=self.query_repository, query=query)
```

```12:20:src/application/use_cases/card/create_card.py
@dataclass(slots=True)
class CreateCardUseCase:
    uow: UnitOfWorkPort
    id_gen: IdGeneratorPort

    def execute(
        self, command: CreateCardCommand
    ) -> AppResult[AppCard, ApplicationError]:
        return handle_create_card(uow=self.uow, id_gen=self.id_gen, command=command)
```

The same shape repeats in `delete_board.py`, `list_boards.py`,
`patch_board.py`, `create_board.py`, `get_card.py`, `patch_card.py`,
`create_column.py`, `delete_column.py`, and `check_readiness.py`. Each
use case therefore lives in two files (one in `use_cases/`, one in
`commands/` or `queries/`) for orchestration that belongs in a single
unit.

The split also makes the orchestration twice as expensive to read: a
contributor following `CreateCardUseCase.execute` has to jump to
`handle_create_card` to find what actually happens.

## What Changes

- Choose a canonical orchestration surface for each use case (single
  class, no free function — see `design.md` for the decision and
  alternatives).
- For every use case under `src/application/use_cases/`:
  - Move the body of the corresponding `handle_*` function into the
    class's `execute` method.
  - Delete the `handle_*` function (and the file if the function was
    its only export — the command/query DTO stays).
- Rename the surviving `commands/<aggregate>/<verb>.py` and
  `queries/<verb>.py` files (or update their `__init__.py`) so they only
  expose DTOs (`CreateCardCommand`, `GetCardQuery`, etc.), not handlers.
- Update every import site (`src/api/dependencies/use_cases.py`,
  `src/api/routers/*`, every test under `tests/unit`, `tests/integration`
  and `tests/architecture`) to call the use-case class directly.
- Add an architecture test under `tests/architecture/` that fails if any
  module under `src/application/use_cases/` re-exports or calls a
  function whose name starts with `handle_` defined in another module of
  the same change set.

The `ApplicationError` enum, HTTP responses, ports, adapters, command/query
DTOs, and domain code are unaffected.

## Capabilities

### New Capabilities
<!-- None. -->

### Modified Capabilities
- `hexagonal-architecture-conformance`: adds a requirement that each
  application use case is a single orchestration unit (one class with
  meaningful `execute` body) and forbids `handle_*` pass-through functions
  living alongside use case classes. Depends on
  `align-project-skeleton-to-hex-skill` having landed first.

## Impact

- Affected code:
  - All 10 files under `src/application/use_cases/{board,card,column,health}/`.
  - Every `handle_*` function definition under
    `src/application/commands/` and `src/application/queries/`. After
    the change these directories contain only DTOs (and possibly empty
    or DTO-only `__init__.py` files).
  - `src/application/commands/__init__.py` and
    `src/application/queries/__init__.py` re-exports.
  - `src/api/dependencies/use_cases.py` (no API change — the deps still
    construct the same use case classes).
  - Tests that import `handle_*` directly:
    `tests/unit/test_*` and any test that targets the function instead
    of the class.
- Affected configuration: none.
- No dependency changes.
- No HTTP / DB / domain behaviour changes — `tests/integration` and
  `tests/e2e` must remain green without modification.
- Order of application:
  1. `align-project-skeleton-to-hex-skill` (introduces the capability).
  2. `unify-domain-error-representation` (changes the Result/error surface
     this change consumes). This change must build on top of the
     unified Result types so the orchestration code uses `Ok`/`Err`/`Result`
     directly inside `execute`.
  3. This change.
