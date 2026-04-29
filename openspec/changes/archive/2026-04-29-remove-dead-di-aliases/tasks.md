## 1. Pre-condition and audit

- [ ] 1.1 Confirm `align-project-skeleton-to-hex-skill` has landed
      (the `hexagonal-architecture-conformance` capability exists at
      `openspec/specs/hexagonal-architecture-conformance/spec.md`).
- [ ] 1.2 Run `rg "container\\.repository|create_repository_for_settings" -n src/ tests/`
      and confirm that no module under `src/` references either
      symbol; the only consumers must be under `tests/`.

## 2. Remove the dead surfaces

- [ ] 2.1 In `src/infrastructure/config/di/container.py`, delete the
      `repository` property from `ConfiguredAppContainer` (lines 36–39
      in the current tree). Update the dataclass / docstring so no
      reference remains.
- [ ] 2.2 In `src/infrastructure/config/di/composition.py`, delete the
      `create_repository_for_settings` function and its docstring
      (lines 70–74 in the current tree).
- [ ] 2.3 In `src/infrastructure/config/di/__init__.py`, remove
      `create_repository_for_settings` from both the `import` block
      and `__all__`.

## 3. Rewrite consuming tests

- [ ] 3.1 In `tests/unit/test_lifespan.py`, replace
      `container.repository` with `container.repositories.kanban`.
- [ ] 3.2 In `tests/unit/test_repository_selection.py`, replace every
      reference to `create_repository_for_settings` with
      `create_kanban_repository_for_settings`. Keep the assertions
      identical otherwise.

## 4. Architecture test for the new invariant

- [ ] 4.1 Add `tests/architecture/test_di_no_unconsumed_compat_aliases.py`
      with marker `@pytest.mark.architecture`. Implementation:
      AST-walk every module under `src.infrastructure.config.di`,
      collect symbols (classes, functions, methods, properties) whose
      docstring matches the case-insensitive phrase
      `"backward-compatible"`, then for each such symbol assert that at
      least one consumer module under `src/` (not `tests/`) imports or
      references it. Use `iter_python_modules("src")` from
      `tests/architecture/conftest.py` and a textual reference search
      (importing it counts; `name.attribute` access counts).
- [ ] 4.2 Verify the test passes against the cleaned-up tree (no
      symbols match the phrase after sections 2 and 3).
- [ ] 4.3 Locally reintroduce one of the deleted aliases plus its
      docstring to confirm the test fails with a clear message;
      revert before commit.

## 5. Final verification

- [ ] 5.1 Run the full matrix:
      `uv run pytest tests/architecture -m architecture`,
      `uv run pytest tests/unit`,
      `uv run pytest tests/integration`,
      `uv run pytest tests/e2e`,
      `uv run lint-imports`,
      `uv run mypy`.
- [ ] 5.2 Run `rg -i "backward[- ]?compatible" -n src/`
      and confirm zero hits.
- [ ] 5.3 Run `openspec status --change remove-dead-di-aliases` and
      confirm the change is ready to archive.
