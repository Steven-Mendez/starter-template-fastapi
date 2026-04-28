## 1. Phase 0 — Architecture Suite Scaffolding (no behavior change)

- [x] 1.1 Create `tests/architecture/__init__.py` and `tests/architecture/conftest.py` exporting helpers `iter_python_modules(package_name)` and `parse_module_ast(path)` shared by all conformance tests
- [x] 1.2 Create `tests/architecture/test_dependency_direction.py` covering domain-purity and application-purity rules from `hexagonal-architecture-conformance` spec; assert each failure message contains the substring `fastapi-hexagonal-architecture:`
- [x] 1.3 Create `tests/architecture/test_naming_conventions.py` covering port/adapter/use-case naming requirements (initially excluding use-case checks until phase 4 lands)
- [x] 1.4 Create `tests/architecture/test_routes_thinness.py` enforcing the "Routes Stay Thin" requirement (`@router.*` handler bodies must call exactly one `*UseCase`, no `src.infrastructure` imports in `src.api.routers`)
- [x] 1.5 Add a `[tool.pytest.ini_options]` marker `architecture` and wire `tests/architecture/` into `make check`, `pre-commit`, and CI (verify the suite is green on the unmodified codebase except the cases that the later phases will fix; mark those as `xfail(strict=True)` with a comment naming the phase that flips them green)
- [x] 1.6 Tighten `pyproject.toml` `[tool.importlinter]` contracts: forbid `pydantic.BaseModel`-style imports in `src.domain` and `src.application`, forbid `fastapi.Depends`/`fastapi.Request`/`fastapi.Response`/`fastapi.HTTPException` outside `src.api`, forbid `src.application.contracts` imports from `src.infrastructure.adapters.outbound.persistence`
- [x] 1.7 Run `lint-imports` and the architecture suite locally; commit the scaffolding so subsequent phases land green by construction

## 2. Phase 1 — Domain Exception Migration

- [x] 2.1 Create `src/domain/kanban/exceptions.py` with `KanbanDomainError`, `BoardNotFoundError`, `ColumnNotFoundError`, `CardNotFoundError`, `InvalidCardMoveError` (all inheriting from `KanbanDomainError`)
- [x] 2.2 Update `src/domain/kanban/models/board.py`: change `Board.delete_column` to raise `ColumnNotFoundError` instead of returning `KanbanError | None`; update the return type to `None`
- [x] 2.3 Update `src/domain/kanban/models/board.py`: change `Board.move_card` to raise `InvalidCardMoveError` (target column missing or specification fails) and `CardNotFoundError` (card missing in source column) instead of returning `KanbanError | None`; update the return type to `None`
- [x] 2.4 Update `src/application/shared/errors.py` `_ERROR_MAP` and add a `from_domain_exception(exc: KanbanDomainError) -> ApplicationError` helper alongside the existing `from_domain_error(error: KanbanError) -> ApplicationError`
- [x] 2.5 Update `src/application/commands/board/delete.py` (and any other call site of `Board.delete_column`/`Board.move_card`) to wrap the domain call in `try/except KanbanDomainError` and translate to `AppErr(from_domain_exception(...))`
- [x] 2.6 Update `src/application/commands/card/patch.py` and `src/application/commands/card/create.py` to translate `KanbanDomainError` exceptions through `from_domain_exception`
- [x] 2.7 Update affected unit tests under `tests/unit/domain/test_board_domain.py` to assert `pytest.raises(...)` instead of inspecting return enums
- [x] 2.8 Add architecture test in `tests/architecture/test_domain_invariants.py` enforcing "no domain method's return type union contains `KanbanError`/`ApplicationError`" and "every `KanbanDomainError` subclass has a translator entry"
- [x] 2.9 Run `pytest`, `lint-imports`, and `mypy` to confirm the migration is clean

## 3. Phase 2 — Persistence Relocation

- [x] 3.1 Create directory tree `src/infrastructure/adapters/outbound/persistence/` with `__init__.py`, `lifecycle.py`, and `sqlmodel/` subpackage with `__init__.py`, `repository.py`, `unit_of_work.py`, `mappers.py`, and `models/` subpackage
- [x] 3.2 Move `src/infrastructure/persistence/sqlmodel_repository.py` → `src/infrastructure/adapters/outbound/persistence/sqlmodel/repository.py` (rename module to drop the `sqlmodel_` prefix since path conveys it)
- [x] 3.3 Move `src/infrastructure/persistence/sqlmodel_uow.py` → `src/infrastructure/adapters/outbound/persistence/sqlmodel/unit_of_work.py`
- [x] 3.4 Move `src/infrastructure/persistence/sqlmodel/mappers.py` → `src/infrastructure/adapters/outbound/persistence/sqlmodel/mappers.py` and `src/infrastructure/persistence/sqlmodel/models/*` → `src/infrastructure/adapters/outbound/persistence/sqlmodel/models/*`
- [x] 3.5 Move `src/infrastructure/persistence/lifecycle.py` → `src/infrastructure/adapters/outbound/persistence/lifecycle.py`
- [x] 3.6 Update every import in `src/infrastructure/config/di/composition.py`, `src/infrastructure/config/di/container.py`, `tests/`, `alembic/env.py`, and any other call site to use the new paths
- [x] 3.7 Delete the now-empty `src/infrastructure/persistence/` directory tree
- [x] 3.8 Update `pyproject.toml` `[tool.importlinter]` contracts and `pyproject.toml` packaging metadata if any package-data refs changed
- [x] 3.9 Add architecture test in `tests/architecture/test_outbound_topology.py` asserting "no module exists directly under `src/infrastructure/` whose name is `persistence`, `messaging`, or `external` (everything must be under `adapters/outbound/`)"
- [x] 3.10 Run `pytest`, `lint-imports`, and `mypy`; confirm `alembic upgrade head` still works against a local database

## 4. Phase 3 — Use-Case Decomposition: Board Aggregate

- [x] 4.1 Create `src/application/use_cases/__init__.py`, `src/application/use_cases/board/__init__.py`
- [x] 4.2 Implement `src/application/use_cases/board/create_board.py` exposing `class CreateBoardUseCase` with constructor `(uow: UnitOfWorkPort, id_gen: IdGeneratorPort, clock: ClockPort)` and a single `execute(command: CreateBoardCommand) -> AppResult[AppBoardSummary, ApplicationError]` method (port the body from `handle_create_board`)
- [x] 4.3 Implement `src/application/use_cases/board/patch_board.py` (`PatchBoardUseCase`)
- [x] 4.4 Implement `src/application/use_cases/board/delete_board.py` (`DeleteBoardUseCase`)
- [x] 4.5 Implement `src/application/use_cases/board/get_board.py` (`GetBoardUseCase`) with constructor `(query_repository: KanbanQueryRepositoryPort)` and `execute(query: GetBoardQuery) -> AppResult[AppBoard, ApplicationError]`
- [x] 4.6 Implement `src/application/use_cases/board/list_boards.py` (`ListBoardsUseCase`)
- [x] 4.7 Refactor `src/api/dependencies.py` into a package `src/api/dependencies/__init__.py` re-exporting from `src/api/dependencies/security.py` (the `WriteApiKeyDep` and container helpers) and `src/api/dependencies/use_cases.py` (factory functions and `Annotated` aliases)
- [x] 4.8 Add per-use-case factory functions and `Annotated` deps for the five board use cases in `src/api/dependencies/use_cases.py` (`get_create_board_use_case`, `CreateBoardUseCaseDep`, etc.)
- [x] 4.9 Update `src/api/routers/boards.py` so each route depends on a single `*UseCaseDep` rather than `CommandHandlersDep`/`QueryHandlersDep`; replace `commands.handle_create_board(...)` with `use_case.execute(...)` etc.
- [x] 4.10 Remove the board branches from `src/application/commands/handlers.py`, `src/application/queries/handlers.py`, `src/application/commands/port.py`, and `src/application/queries/port.py` (still leaving column/card/health entries until phase 4 finishes)
- [x] 4.11 Update unit tests targeting board commands/queries: replace `KanbanCommandHandlers`-based tests with per-use-case unit tests that instantiate the class with fake ports
- [x] 4.12 Run full test suite, `lint-imports`, `mypy`

## 5. Phase 4 — Use-Case Decomposition: Column, Card, Health Aggregates

- [x] 5.1 Create `src/application/use_cases/column/__init__.py` with `CreateColumnUseCase` and `DeleteColumnUseCase`; mirror tasks 4.2–4.4 for column endpoints in `src/api/routers/columns.py` and `src/api/dependencies/use_cases.py`
- [x] 5.2 Create `src/application/use_cases/card/__init__.py` with `CreateCardUseCase`, `PatchCardUseCase`, `GetCardUseCase`; mirror tasks 4.2–4.5 for card endpoints in `src/api/routers/cards.py`
- [x] 5.3 Create `src/application/use_cases/health/check_readiness.py` with `CheckReadinessUseCase` (constructor `(readiness: ReadinessProbe)`, `execute(query: HealthCheckQuery) -> bool`); rewire `src/api/routers/health.py` to use it
- [x] 5.4 Delete `src/application/commands/handlers.py`, `src/application/commands/port.py`, `src/application/queries/handlers.py`, `src/application/queries/port.py`, and update `src/application/commands/__init__.py` and `src/application/queries/__init__.py` re-exports accordingly
- [x] 5.5 Delete `KanbanCommandHandlers` and `KanbanQueryHandlers` references from `src/infrastructure/config/di/container.py`; replace with per-use-case factory functions used by `src/api/dependencies/use_cases.py`
- [x] 5.6 Delete `CommandHandlersDep`, `QueryHandlersDep`, `CommandHandlersFactory`, `KanbanCommandInputPort`, `KanbanQueryInputPort` from any remaining import sites
- [x] 5.7 Migrate every remaining unit test to reference the new use-case classes
- [x] 5.8 Run full test suite, `lint-imports`, `mypy`

## 6. Phase 5 — Conformance Suite Hardening

- [x] 6.1 Flip every `xfail(strict=True)` test added in phase 0 to plain assertions; remove the `xfail` markers
- [x] 6.2 Add `tests/architecture/test_use_case_cohesion.py` enforcing: each file under `src/application/use_cases/<aggregate>/<name>.py` defines exactly one class whose name ends in `UseCase`, the class has exactly one public method named `execute`, the constructor parameter type annotations resolve only to `*Port` symbols or other `*UseCase` symbols
- [x] 6.3 Add `tests/architecture/test_no_aggregator_ports.py` asserting that no `Protocol` class declares two or more methods following the `handle_<verb>_<noun>` pattern for distinct nouns, and that the symbols `KanbanCommandInputPort`, `KanbanQueryInputPort`, `KanbanCommandHandlers`, `KanbanQueryHandlers` are not importable from `src.application` or any submodule
- [x] 6.4 Add `tests/architecture/test_pydantic_confined_to_api.py` walking the AST of every file outside `src/api/` and failing if any class inherits from `pydantic.BaseModel` or `pydantic.RootModel`
- [x] 6.5 Add `tests/architecture/test_inbound_does_not_import_domain_exceptions.py` asserting no module under `src/api/` imports `KanbanDomainError` or any of its subclasses
- [x] 6.6 Add `tests/architecture/test_use_case_no_fastapi.py` asserting no module under `src/application/use_cases/` imports from `fastapi`, `starlette`, `sqlmodel`, `sqlalchemy`, `httpx`, or `src.infrastructure`
- [x] 6.7 Add `tests/architecture/test_skill_checklist_coverage.py` that statically parses `.opencode/skills/fastapi-hexagonal-architecture/SKILL.md` ("Review Checklist" section), enumerates each bullet, and asserts there exists at least one architecture test whose docstring contains the bullet text or a stable identifier referenced from the bullet (this is the meta-test that ensures the suite stays exhaustive)
- [x] 6.8 Run `pytest`, `lint-imports`, `mypy`; full architecture suite must be green

## 7. Phase 6 — Documentation, CI, and Archive Readiness

- [x] 7.1 Update `hex-design-guide.md` to reference the new layout (use-case classes, persistence under `adapters/outbound/persistence`, domain exceptions) and link to the architecture suite as the conformance gate
- [x] 7.2 Update the `fastapi-hexagonal-architecture` skill's `## Practical Import Checks` section in `.opencode/skills/fastapi-hexagonal-architecture/SKILL.md` to point to `pytest tests/architecture && lint-imports` instead of ad-hoc `grep` commands
- [x] 7.3 Add a "Conformance" section to `README.md` describing the architecture suite, how to run it, and what to do when it fails
- [x] 7.4 Verify CI configuration (`.github/workflows/`) executes the architecture suite and `lint-imports` on every PR
- [x] 7.5 Run `openspec validate hex-conformance-finalization` and resolve any reported issues
- [x] 7.6 Run the full quality gate (`pytest`, `lint-imports`, `mypy`, `ruff check .`, `pre-commit run --all-files`); confirm 100% pass
- [ ] 7.7 Open a PR titled `chore(arch): finalize hex conformance via use-case decomposition + automated suite` summarizing the breaking changes and pointing to the design doc
- [ ] 7.8 After merge, archive the change with `openspec archive hex-conformance-finalization` so the four spec files (two new, two modified) are merged into the `openspec/specs/` source of truth
