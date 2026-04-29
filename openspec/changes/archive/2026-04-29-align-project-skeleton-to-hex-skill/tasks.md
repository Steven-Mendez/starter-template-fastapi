## 1. Move FastAPI entrypoint to `src/main.py`

- [ ] 1.1 Move `./main.py` to `src/main.py` (preserve content verbatim, then adjust imports if needed).
- [ ] 1.2 Verify `src/main.py` imports still resolve (`src.api...`, `src.config.settings` for now — section 2 will rewrite these).
- [ ] 1.3 Update `pyproject.toml`: remove or replace `pythonpath = ["."]` (try removing; if `pytest` collection breaks, set `pythonpath = ["src"]`).
- [ ] 1.4 Update `Dockerfile`: change uvicorn target to `src.main:app`.
- [ ] 1.5 Update `docker-compose.yml`: same uvicorn target update.
- [ ] 1.6 Update `Makefile` targets that invoke uvicorn or reference `main:app`.
- [ ] 1.7 Update `README.md` deployment / quickstart sections to use `src.main:app` and document the breaking change.
- [ ] 1.8 Update CI workflows under `.github/workflows/` if they invoke uvicorn or import `main`.
- [ ] 1.9 Confirm `alembic/env.py` does not import from the old `main.py`; update if it does.
- [ ] 1.10 Run `uv run pytest tests/architecture -m architecture` and `uv run lint-imports`; ensure both green.
- [ ] 1.11 Smoke-test `uvicorn src.main:app` locally (boot only).

## 2. Relocate `AppSettings` into `src/infrastructure/config/`

- [ ] 2.1 Create `src/infrastructure/config/settings.py` containing the current `AppSettings` and `get_settings` from `src/config/settings.py` (verbatim).
- [ ] 2.2 Decide whether `src/infrastructure/config/__init__.py` should re-export `AppSettings`/`get_settings`; either is fine — pick one and apply consistently.
- [ ] 2.3 Update `src/api/dependencies/security.py` to import `AppSettings` from the new location.
- [ ] 2.4 Update `src/infrastructure/config/di/composition.py` and `src/infrastructure/config/di/container.py` to import from the new location.
- [ ] 2.5 Update `src/main.py` to import `AppSettings`/`get_settings` from `src.infrastructure.config.settings` (or the chosen re-export path).
- [ ] 2.6 Run `rg "src\\.config" -n` across the whole repo and update every remaining reference (tests, alembic, docs, scripts).
- [ ] 2.7 Delete `src/config/settings.py` and `src/config/__init__.py`; remove the now-empty `src/config/` directory.
- [ ] 2.8 Edit `pyproject.toml`: remove `"src.config"` from `forbidden_modules` in the "Domain layer" and "Application layer" import-linter contracts.
- [ ] 2.9 Run `uv run lint-imports`; expect 6 contracts kept.
- [ ] 2.10 Run `uv run pytest tests/architecture tests/unit` and confirm green.
- [ ] 2.11 Run `uv run pytest tests/integration` (testcontainers) and confirm green.

## 3. Remove `KanbanRepositoryPort` aggregator from application

- [ ] 3.1 Run `rg "KanbanRepositoryPort" -n` to inventory every consumer (expected: `src/application/ports/kanban_repository.py`, `src/application/ports/__init__.py`, `src/infrastructure/config/di/composition.py`, `src/infrastructure/adapters/outbound/persistence/sqlmodel/repository.py`, `tests/unit/test_hexagonal_boundaries.py`).
- [ ] 3.2 In `src/infrastructure/adapters/outbound/persistence/sqlmodel/repository.py`, change `_BaseSQLModelKanbanRepository(KanbanRepositoryPort)` to inherit `KanbanQueryRepositoryPort`, `KanbanCommandRepositoryPort`, `KanbanLookupRepositoryPort` directly; update imports.
- [ ] 3.3 In `src/infrastructure/config/di/composition.py`, redefine `ManagedKanbanRepositoryPort` to inherit the three segregated ports plus `ReadinessProbe` and `ClosableResource`; remove the import of `KanbanRepositoryPort`.
- [ ] 3.4 Update `tests/unit/test_hexagonal_boundaries.py` to drop `KanbanRepositoryPort` references and assert against the segregated ports instead.
- [ ] 3.5 Delete `src/application/ports/kanban_repository.py`.
- [ ] 3.6 Remove `KanbanRepositoryPort` from `src/application/ports/__init__.py` (`__all__` and import line).
- [ ] 3.7 Run `uv run lint-imports` and `uv run pytest tests/architecture tests/unit tests/integration` — all green.

## 4. Lock the rule with an architecture test

- [ ] 4.1 Add `tests/architecture/test_no_repository_aggregator_ports.py` with marker `@pytest.mark.architecture` that walks `iter_python_modules("src.application.ports")`, inspects each `Protocol` `ClassDef`, and fails if it inherits from more than one base whose `id`/`attr` ends in `RepositoryPort`.
- [ ] 4.2 Verify the test passes against the cleaned-up tree.
- [ ] 4.3 Verify the test fails when a temporary aggregator Protocol is reintroduced (manual local check; revert before commit).

## 5. Final verification and archive readiness

- [ ] 5.1 Run the full matrix: `uv run pytest tests/architecture -m architecture`, `uv run pytest tests/unit`, `uv run pytest tests/integration`, `uv run pytest tests/e2e`, `uv run lint-imports`, `uv run mypy`.
- [ ] 5.2 Smoke-test `docker compose up` (or equivalent) end-to-end against the new entrypoint.
- [ ] 5.3 Update `README.md` changelog / migration note documenting the breaking deployment change (`uvicorn main:app` → `uvicorn src.main:app`).
- [ ] 5.4 Run `openspec status --change align-project-skeleton-to-hex-skill` and confirm the change is ready to archive.
