## Context

The kanban domain currently exposes failures in two parallel forms:

- **Result-with-enum**: repositories return `Result[Board, KanbanError]`
  where `KanbanError` is a `StrEnum` declared in `src/domain/shared/errors.py`.
- **Exceptions**: domain methods such as `Column.insert_card`,
  `Board.move_card`, etc. raise subclasses of `KanbanDomainError`
  declared in `src/domain/kanban/exceptions.py`.

Both encode the same four failures (`BOARD_NOT_FOUND`, `COLUMN_NOT_FOUND`,
`CARD_NOT_FOUND`, `INVALID_CARD_MOVE`). Application code therefore has
two translation paths into `ApplicationError`:

```37:62:src/application/commands/card/create.py
        board_result = uow.commands.find_by_id(board_id)
        if isinstance(board_result, Err):
            return AppErr(from_domain_error(board_result.error))
        ...
        try:
            col.insert_card(card)
        except KanbanDomainError as exc:
            return AppErr(from_domain_exception(exc))
```

In addition:

- `KanbanError` lives under `domain/shared/`, contradicting the skill's
  layout where `shared/` is reserved for cross-aggregate concepts.
- `application/shared/errors.py` is named "shared" but knows only kanban.
- `application/shared/result.py` declares `AppOk`/`AppErr`/`AppResult`,
  which are structural clones of the domain `Ok`/`Err`/`Result` with no
  added semantics.

The result is duplicated representation, duplicated translation, and two
misnamed `shared/` namespaces.

## Goals / Non-Goals

**Goals:**
- One canonical form for kanban domain failures.
- Aggregate-specific errors live under `src/domain/kanban/` only.
- `application/shared/` contains only genuinely cross-cutting code.
- A single `Result` type (the domain one) reused everywhere; no application
  clone.
- Architecture tests that prevent regression of the above.

**Non-Goals:**
- Changing the public `ApplicationError` enum values, their HTTP mappings,
  or the resulting Problem Details payloads. The inbound contract stays
  stable.
- Refactoring use case orchestration logic (only signatures and translation
  plumbing change).
- Touching the domain entities (`Board`, `Column`, `Card`) beyond changing
  what they raise / return for failures.
- Splitting kanban into smaller bounded contexts.

## Decisions

### D1 — Choose `Result[T, E]` with a per-aggregate error enum as the canonical form

**Decision:** keep the Result-based representation. Domain failures cross
the layer boundary as `Result[T, KanbanError]` (with `KanbanError` redefined
under `src/domain/kanban/`). Domain methods that currently raise
`KanbanDomainError` (e.g. `Column.insert_card`, `Board.move_card`) are
refactored to return `Result[..., KanbanError]`. The `KanbanDomainError`
hierarchy is removed.

**Rationale:**

- The Result form is already the surface of every repository port
  (`KanbanCommandRepositoryPort.find_by_id`, `.remove`,
  `KanbanQueryRepositoryPort.find_by_id`, `.find_card_by_id`). Picking
  Result keeps **all** outbound contracts uniform.
- The existing `Result`/`Ok`/`Err` types in `src/domain/shared/result.py`
  already ship a complete helper suite (`map`, `map_err`, `and_then`,
  `unwrap`, `unwrap_err`, `expect`, `expect_err`, `expect_ok`, `is_ok`,
  `is_err`). The exception form has no equivalent infrastructure.
- Use cases already lean Result-first: `AppResult[T, ApplicationError]` is
  the return type of every `handle_*` function and the value carried by
  `AppOk`/`AppErr` matches Result mechanics.
- Eliminating exceptions removes the `try/except KanbanDomainError` blocks
  inside `handle_create_card` / `handle_patch_card` / `handle_delete_column`,
  giving every application path the same shape (pattern-match on `Ok/Err`).
- Errors-as-values are easier to test exhaustively (`StrEnum` membership
  checks) and to map exhaustively at the API boundary (the existing
  `_APPLICATION_ERROR_HTTP_MAP` exhaustiveness check at
  `src/api/routers/_errors.py:45` is precisely this pattern).

**Alternatives considered:**

- **Exceptions-only.** Matches the literal skill example
  (`class DomainError(Exception)`). Pros: more idiomatic in classic
  Python; the skill text uses it. Cons: we would have to rewrite every
  repository port to raise instead of return `Result`, drop a sizeable
  `Result` helper module, and lose the exhaustiveness guarantee provided
  by the enum mapping check. The diff is significantly larger than D1's,
  and the code we keep ends up less type-safe (Python exceptions don't
  appear in signatures). The skill itself is permissive about style
  ("Acceptable Shortcuts" — "Perfect purity is not always required").

- **Keep both, formalise the dual contract.** Rejected: the user explicitly
  asked to remove duplications; keeping both would only add ceremony
  (translation tables, doc rules) without value.

**Consequence for the rest of the design:** every reference below assumes
Result-only.

### D2 — Move `KanbanError` to `src/domain/kanban/errors.py`

`KanbanError` (the enum) is the canonical kanban failure type after D1.
Move it from `src/domain/shared/errors.py` to a new file
`src/domain/kanban/errors.py`. Delete `src/domain/shared/errors.py`. Update
`src/domain/shared/__init__.py` and `src/domain/__init__.py` to drop
`KanbanError` from their exports; consumers import from
`src.domain.kanban.errors` directly (or via `src.domain.kanban.__init__` if
that package re-exports it).

`src/domain/kanban/exceptions.py` is removed entirely after D1; all
`KanbanDomainError` subclasses disappear.

**Alternatives considered:**

- Merge `errors.py` into the existing `exceptions.py` and rename the file.
  Rejected because `exceptions.py` literally describes Python exceptions;
  the surviving module holds an enum, not an exception type.

### D3 — Remove `src/application/shared/result.py` and reuse the domain `Result`

Delete `AppOk`, `AppErr`, `AppResult` from
`src/application/shared/result.py`. Update every application module that
currently imports them to import `Ok`, `Err`, and `Result` from
`src.domain.shared.result`. The application return type
`AppResult[T, ApplicationError]` becomes
`Result[T, ApplicationError]`.

`src/application/shared/__init__.py` drops the `AppOk`, `AppErr`,
`AppResult` re-exports.

**Why this is allowed:** the inward-dependency rule (skill lines 51–56)
permits application to depend on domain. `Result`, `Ok`, `Err` are
generic, layer-agnostic data types — they are the single most natural
piece of cross-layer code.

**Alternatives considered:**

- Keep `AppResult` as a `TypeAlias` (`type AppResult[T, E] = Result[T, E]`).
  Rejected because the alias adds no value and obscures the canonical
  origin in import lists.

### D4 — Move kanban-specific application errors out of `application/shared/`

Move `src/application/shared/errors.py` (which only knows kanban) to
`src/application/kanban/errors.py`. Update all importers
(`src/application/commands/**`, `src/application/queries/**`,
`src/application/use_cases/**`, `src/api/routers/_errors.py`,
`src/application/shared/__init__.py`).

After this move, `src/application/shared/` contains only truly
cross-cutting code: `result_*` helpers (if any are added later) and
`ReadinessProbe`. `ReadinessProbe` is genuinely cross-cutting (used by
health checks across any future bounded context) and stays.

`from_domain_error` becomes the only translation function (after D1
eliminates `from_domain_exception`).

**Alternatives considered:**

- Rename `ApplicationError` → `KanbanApplicationError` and keep it in
  `application/shared/`. Rejected: the symbol is fine; the **location**
  is what's wrong. Renaming hides the real problem.
- Keep `application/shared/errors.py` as a thin re-export layer for backward
  compatibility. Rejected: there are no external consumers; the project is
  a single repo.

### D5 — Architecture tests to prevent regression

Add two tests under `tests/architecture/`, both marked
`@pytest.mark.architecture`:

1. `test_domain_shared_is_aggregate_neutral.py` — walks
   `iter_python_modules("src.domain.shared")` and fails if any module name
   matches a known aggregate stem (today: `kanban`, but the test reads the
   list from `src.domain` subpackages dynamically) or if any
   `ast.ClassDef`/`ast.Assign` defines a name that contains the stem of an
   aggregate (e.g. `KanbanError`, `KanbanFoo`).

2. `test_application_shared_is_aggregate_neutral.py` — walks
   `iter_python_modules("src.application.shared")` and fails if any
   `ImportFrom` targets a module under `src.domain.<aggregate>` for any
   aggregate name discovered under `src.domain/`. Imports of
   `src.domain.shared.*` are allowed.

These two tests close the loop on D2 and D4 respectively.

**Alternatives considered:**

- A single test covering both. Rejected: the failure messages would be
  harder to read; one test per invariant is the existing convention in
  `tests/architecture/`.

## Risks / Trade-offs

- **[Risk] Removing `KanbanDomainError` breaks existing test fixtures or
  unit tests that assert exception types.**
  → Mitigation: `tests/unit/domain/test_board_domain.py`,
  `tests/unit/test_specification_pattern.py`, and similar files will need
  to assert against `Err(KanbanError.X)` instead of
  `pytest.raises(BoardNotFoundError)`. Tasks list updates these explicitly;
  the integration / e2e suites should not be affected.

- **[Risk] Some domain methods may currently raise `ValueError` or other
  generic exceptions for invariant violations not represented in
  `KanbanError`.**
  → Mitigation: implementation step audits every `raise` in `src/domain/`
  before D1. Any failure case missing from `KanbanError` is added to the
  enum (and to `ApplicationError` plus the HTTP map) in the same change.

- **[Risk] `ApplicationError.UNMAPPED_DOMAIN_ERROR` becomes unreachable
  after D1 (no exceptions left to misclassify).**
  → Mitigation: keep the value as a defensive fallback for genuinely
  unexpected `KanbanError` additions that ship before the application
  catches up. Document its purpose in the source.

- **[Trade-off] Result-style propagation pushes more `match` blocks into
  use cases.** Domain methods that today simply raise will now return
  `Result`, forcing callers to pattern-match. For invariants that are
  triggered very rarely in practice, this is more verbose than a
  `try/except`. We accept the verbosity in exchange for type-checkable
  signatures and a single failure model.

- **[Trade-off] Changing repository ports' return types is technically a
  contract change for any future external adapter.** No external adapter
  exists today, but if one is added later, it must conform to the unified
  Result-based signature.

## Migration Plan

1. **Land `align-project-skeleton-to-hex-skill` first.** This change
   modifies the `hexagonal-architecture-conformance` spec; that spec must
   exist in `openspec/specs/` before this change can be archived.

2. **Domain consolidation (D1 + D2):**
   - Audit every `raise` in `src/domain/`; for each failure case not yet
     in `KanbanError`, add it.
   - Move `KanbanError` to `src/domain/kanban/errors.py`.
   - Rewrite domain methods that currently raise `KanbanDomainError`
     subclasses to return `Result[T, KanbanError]` instead. Update
     `src/domain/kanban/__init__.py`.
   - Delete `src/domain/kanban/exceptions.py`. Update tests under
     `tests/unit/domain/` and `tests/unit/test_specification_pattern.py`.
   - Delete `src/domain/shared/errors.py`. Update
     `src/domain/shared/__init__.py` and `src/domain/__init__.py`.

3. **Application result unification (D3):**
   - Replace every import of `AppOk`/`AppErr`/`AppResult` with
     `Ok`/`Err`/`Result` from `src.domain.shared.result` across
     `src/application/`. Update return type hints.
   - Delete `src/application/shared/result.py` and remove the re-exports
     from `src/application/shared/__init__.py`.

4. **Application errors relocation (D4):**
   - Move `src/application/shared/errors.py` to
     `src/application/kanban/errors.py` (creating the package). Adjust
     imports across `src/application/commands/**`,
     `src/application/queries/**`, `src/application/use_cases/**`, and
     `src/api/routers/_errors.py`.
   - Drop `from_domain_exception` and `_EXCEPTION_ERROR_MAP` (made
     redundant by D1).
   - Update `src/application/shared/__init__.py` so it only exposes
     genuinely cross-cutting symbols.

5. **Architecture tests (D5):**
   - Add `tests/architecture/test_domain_shared_is_aggregate_neutral.py`.
   - Add
     `tests/architecture/test_application_shared_is_aggregate_neutral.py`.
   - Verify both tests pass.

6. **Verification:** run `uv run pytest tests/architecture -m architecture`,
   `uv run pytest tests/unit`, `uv run pytest tests/integration`,
   `uv run pytest tests/e2e`, `uv run lint-imports`, `uv run mypy`.

**Rollback:** revert the change PR. No data, schema, or HTTP contract
involvement.

## Open Questions

- Should `src/application/kanban/__init__.py` re-export `ApplicationError`
  for ergonomic imports, or should callers always use the explicit
  `src.application.kanban.errors` path? Decide at implementation time —
  the architecture tests don't care.
- After D1, does any path still raise `KanbanDomainError`? Verify via
  `rg "raise " src/domain` after D1 lands locally and before merging.
