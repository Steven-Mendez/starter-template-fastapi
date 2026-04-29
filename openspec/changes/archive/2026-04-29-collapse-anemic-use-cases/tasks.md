## 1. Pre-conditions and audit

- [ ] 1.1 Confirm `align-project-skeleton-to-hex-skill` and
      `unify-domain-error-representation` have landed (their delta specs
      are merged into `openspec/specs/hexagonal-architecture-conformance/spec.md`).
- [ ] 1.2 Run `rg "from src.application.(commands|queries).*import (handle_)" -n src/ tests/`
      and inventory every consumer of `handle_*` functions.
- [ ] 1.3 Run `rg "^def handle_" -n src/application/commands src/application/queries`
      to enumerate every `handle_*` function to migrate.
- [ ] 1.4 Verify no `handle_*` function is imported by another `handle_*`
      function (cross-handler composition). If any cross-imports exist,
      plan their landing in a private `_helpers.py` under the relevant
      `use_cases/<aggregate>/` package.

## 2. Migrate `board` use cases

- [ ] 2.1 `CreateBoardUseCase`: move the body of `handle_create_board`
      into `CreateBoardUseCase.execute`. Update imports. Delete the
      function from `src/application/commands/board/create.py`. Run
      `uv run pytest tests/unit -k board` until green.
- [ ] 2.2 `PatchBoardUseCase`: same treatment for `handle_patch_board`.
- [ ] 2.3 `DeleteBoardUseCase`: same for `handle_delete_board`.
- [ ] 2.4 `GetBoardUseCase`: same for `handle_get_board` (in
      `src/application/queries/get_board.py`).
- [ ] 2.5 `ListBoardsUseCase`: same for `handle_list_boards` (in
      `src/application/queries/list_boards.py`).
- [ ] 2.6 Update `src/application/commands/__init__.py` and
      `src/application/queries/__init__.py` so they re-export only
      DTOs (no `handle_*`).
- [ ] 2.7 Run `uv run pytest tests/unit tests/integration -k board`.

## 3. Migrate `card` use cases

- [ ] 3.1 `CreateCardUseCase`: collapse `handle_create_card` into
      `execute`. Adjust imports.
- [ ] 3.2 `PatchCardUseCase`: collapse `handle_patch_card` into
      `execute`. After `unify-domain-error-representation`, the
      previous `try/except KanbanDomainError` is already gone — verify
      and remove any leftover.
- [ ] 3.3 `GetCardUseCase`: collapse `handle_get_card` into `execute`.
- [ ] 3.4 Run `uv run pytest tests/unit tests/integration -k card`.

## 4. Migrate `column` use cases

- [ ] 4.1 `CreateColumnUseCase`: collapse `handle_create_column` into
      `execute`.
- [ ] 4.2 `DeleteColumnUseCase`: collapse `handle_delete_column` into
      `execute`.
- [ ] 4.3 Run `uv run pytest tests/unit tests/integration -k column`.

## 5. Migrate `health` use case

- [ ] 5.1 `CheckReadinessUseCase`: collapse `handle_health_check` into
      `execute` (return type stays `bool`).
- [ ] 5.2 Run `uv run pytest tests/unit -k health`.

## 6. Test rewrites

- [ ] 6.1 Locate every test (from inventory in 1.2) that imports a
      `handle_*` function. Rewrite each to instantiate the use case
      class with fakes/mocks and call `execute(...)` instead.
- [ ] 6.2 Confirm `tests/unit/` and `tests/integration/` are green.

## 7. Architecture test for the new shape

- [ ] 7.1 Add `tests/architecture/test_use_cases_have_no_handle_passthrough.py`.
      Implementation: AST-walk every module under
      `src.application.use_cases`, locate classes whose name ends in
      `UseCase`, locate `execute` methods, and fail if the body is a
      single `Return` whose value is a `Call` to a function whose
      name starts with `handle_` defined in another module.
- [ ] 7.2 Extend or add a sibling assertion that fails if any function
      whose name starts with `handle_` is defined under
      `src/application/commands/` or `src/application/queries/`.
- [ ] 7.3 Verify the test passes against the migrated tree. Locally
      reintroduce a single pass-through to confirm the test fails with
      a clear message; revert.

## 8. Final verification

- [ ] 8.1 Run the full matrix:
      `uv run pytest tests/architecture -m architecture`,
      `uv run pytest tests/unit`,
      `uv run pytest tests/integration`,
      `uv run pytest tests/e2e`,
      `uv run lint-imports`,
      `uv run mypy`.
- [ ] 8.2 Run `rg "handle_" -n src/application` and confirm only
      method/private references remain (no module-level handler
      functions).
- [ ] 8.3 Smoke-test `uvicorn src.main:app` and exercise one POST and
      one GET endpoint to verify behaviour is unchanged.
- [ ] 8.4 Run `openspec status --change collapse-anemic-use-cases` and
      confirm the change is ready to archive.
