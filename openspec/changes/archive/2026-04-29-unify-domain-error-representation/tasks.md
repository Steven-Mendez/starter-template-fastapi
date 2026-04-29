## 1. Audit and prepare

- [ ] 1.1 Confirm `align-project-skeleton-to-hex-skill` has landed and
      `openspec/specs/hexagonal-architecture-conformance/spec.md` exists.
- [ ] 1.2 Run `rg "raise " src/domain` and list every exception class
      raised by domain methods. Verify each maps to an existing
      `KanbanError` value; if any failure case is missing from the enum,
      add it (along with the corresponding `ApplicationError` value and
      HTTP mapping in `src/api/routers/_errors.py`).
- [ ] 1.3 Run `rg "KanbanDomainError|BoardNotFoundError|ColumnNotFoundError|CardNotFoundError|InvalidCardMoveError" -n` and inventory every consumer (production and tests).
- [ ] 1.4 Run `rg "AppOk|AppErr|AppResult" -n src/ tests/` and inventory
      every consumer.
- [ ] 1.5 Run `rg "from_domain_exception|_EXCEPTION_ERROR_MAP" -n` and
      inventory every consumer.

## 2. Move `KanbanError` into `src/domain/kanban/`

- [ ] 2.1 Create `src/domain/kanban/errors.py` containing the `KanbanError`
      enum (verbatim copy of the current `src/domain/shared/errors.py`
      content).
- [ ] 2.2 Update `src/domain/kanban/__init__.py` to re-export
      `KanbanError` (decide whether to also re-export it from a higher
      level — keep imports explicit at use sites).
- [ ] 2.3 Update every consumer detected in 1.3 to import from
      `src.domain.kanban.errors` (or via `src.domain.kanban` if
      re-exported). Affects, at minimum:
      `src/application/ports/kanban_command_repository.py`,
      `src/application/ports/kanban_query_repository.py`,
      `src/application/ports/kanban_lookup_repository.py`,
      `src/application/shared/errors.py`,
      `src/infrastructure/adapters/outbound/persistence/sqlmodel/repository.py`,
      `src/infrastructure/adapters/outbound/query/kanban_query_repository_view.py`,
      and the relevant tests.
- [ ] 2.4 Delete `src/domain/shared/errors.py`.
- [ ] 2.5 Update `src/domain/shared/__init__.py` and
      `src/domain/__init__.py` to drop `KanbanError` from imports and
      `__all__`.
- [ ] 2.6 Run `uv run pytest tests/architecture -m architecture` and
      `uv run lint-imports`; both should remain green.

## 3. Convert domain methods to Result-based failures

- [ ] 3.1 Refactor `Column.insert_card`, `Board.move_card`, and any other
      domain method that currently raises `KanbanDomainError` (or a
      subclass) to return `Result[T, KanbanError]` instead. Update
      callers within domain modules.
- [ ] 3.2 Update domain unit tests
      (`tests/unit/domain/test_board_domain.py`,
      `tests/unit/test_specification_pattern.py`, etc.) to assert
      against `Err(KanbanError.<CASE>)` rather than
      `pytest.raises(<DomainExceptionClass>)`.
- [ ] 3.3 Delete `src/domain/kanban/exceptions.py`. Update
      `src/domain/kanban/__init__.py` to drop the exception re-exports.

## 4. Update application command handlers to handle Result instead of exceptions

- [ ] 4.1 In `src/application/commands/card/create.py`, replace the
      `try/except KanbanDomainError` block around `col.insert_card(card)`
      with a `match` on the returned `Result`. Use `from_domain_error`.
- [ ] 4.2 Apply the same change to
      `src/application/commands/card/patch.py`,
      `src/application/commands/column/delete.py`, and any other handler
      that currently catches `KanbanDomainError`.
- [ ] 4.3 Remove `from_domain_exception` and `_EXCEPTION_ERROR_MAP` from
      `src/application/shared/errors.py` (its successor; see section 6).
- [ ] 4.4 Run `uv run pytest tests/unit` until green.

## 5. Unify the Result type (delete `AppOk`/`AppErr`/`AppResult`)

- [ ] 5.1 Replace every import of `AppOk`/`AppErr`/`AppResult` with
      `Ok`/`Err`/`Result` from `src.domain.shared.result`. Affects every
      `handle_*` function and use case.
- [ ] 5.2 Update return type hints from `AppResult[T, ApplicationError]`
      to `Result[T, ApplicationError]`.
- [ ] 5.3 Update `src/application/use_cases/**` and `src/api/routers/*`
      to pattern-match on `Ok`/`Err` instead of `AppOk`/`AppErr`.
- [ ] 5.4 Delete `src/application/shared/result.py`.
- [ ] 5.5 Update `src/application/shared/__init__.py` to drop the
      `AppOk`/`AppErr`/`AppResult` re-exports.
- [ ] 5.6 Run `uv run pytest tests/unit tests/integration` until green.

## 6. Move kanban-specific application errors out of `application/shared/`

- [ ] 6.1 Create `src/application/kanban/__init__.py` and
      `src/application/kanban/errors.py`. Move the contents of
      `src/application/shared/errors.py` (the `ApplicationError` enum,
      `_ERROR_MAP`, and `from_domain_error`) to the new file.
- [ ] 6.2 Update every importer of `ApplicationError`, `from_domain_error`
      (and previously `from_domain_exception`) to point at
      `src.application.kanban.errors`. At minimum:
      `src/application/commands/**`, `src/application/queries/**`,
      `src/application/use_cases/**`, `src/application/shared/__init__.py`,
      `src/api/routers/_errors.py`.
- [ ] 6.3 Delete `src/application/shared/errors.py`.
- [ ] 6.4 Update `src/application/shared/__init__.py` to expose only
      genuinely cross-cutting symbols (e.g. `ReadinessProbe`).
- [ ] 6.5 Run `uv run pytest tests/unit tests/integration` until green.

## 7. Architecture tests to lock the invariants

- [ ] 7.1 Add `tests/architecture/test_domain_shared_is_aggregate_neutral.py`
      that walks `iter_python_modules("src.domain.shared")`, discovers
      aggregate stems by listing immediate subpackages of `src.domain`
      (excluding `shared`), and fails if any module name, class name, or
      top-level assignment in `domain/shared/` contains an aggregate stem.
- [ ] 7.2 Add `tests/architecture/test_application_shared_is_aggregate_neutral.py`
      that walks `iter_python_modules("src.application.shared")`,
      inspects every `Import`/`ImportFrom`, and fails if any target
      module starts with `src.domain.<aggregate>.` for an aggregate
      discovered under `src/domain/` other than `shared`.
- [ ] 7.3 Extend an existing or new architecture test to fail if any
      class declared anywhere under `src.application` is named `AppOk`,
      `AppErr`, or `AppResult`.
- [ ] 7.4 Verify all three new assertions pass against the cleaned-up
      tree. Manually reintroduce a violation locally to confirm each
      test fails with a clear message; revert before commit.

## 8. Final verification

- [ ] 8.1 Run `uv run pytest tests/architecture -m architecture`,
      `uv run pytest tests/unit`, `uv run pytest tests/integration`,
      `uv run pytest tests/e2e`, `uv run lint-imports`, `uv run mypy`.
- [ ] 8.2 Verify `rg "AppOk|AppErr|AppResult|KanbanDomainError|from_domain_exception" -n src/ tests/`
      returns no production hits (test hits should also be gone).
- [ ] 8.3 Smoke-test `uvicorn src.main:app` and exercise one POST and one
      GET endpoint to confirm Problem Details responses are unchanged.
- [ ] 8.4 Run `openspec status --change unify-domain-error-representation`
      and confirm the change is ready to archive.
