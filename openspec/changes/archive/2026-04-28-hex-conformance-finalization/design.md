## Context

The codebase has already absorbed four hex-architecture changes (`hex-adapter-restructure-and-contract-testing`, `hex-error-boundaries`, `hex-port-segregation-and-mapping`, `hex-transaction-boundary-unification`). The dependency direction (`api → application → domain`, `infrastructure → application/domain`) is enforced by `import-linter`, the unit-of-work owns transactions, error translation lives at a single boundary, and ports are segregated into command / query / lookup. Despite this, every conformance review against `.opencode/skills/fastapi-hexagonal-architecture/SKILL.md` keeps surfacing "gaps" and the agent reports always feel partial.

A close read of the skill against the current code shows that what is actually missing is concentrated in three places:

1. **Anti-Pattern 6 — Generic service objects with too many methods.** `KanbanCommandInputPort` exposes seven `handle_*` methods on a single port and `KanbanQueryHandlers` exposes four. The skill explicitly names this as an anti-pattern and prescribes intention-revealing per-use-case classes (`PlaceOrderUseCase`, etc.).
2. **Domain return-sentinel mixing.** `Board.delete_column` and `Board.move_card` return `KanbanError | None` instead of raising domain exceptions. The skill is explicit: domain rule violations belong in domain exceptions, not return values.
3. **Subjective conformance review.** The skill ships a 17-item review checklist that has been used as a manual prompt to the agent. There is no machine guard for it, so every iteration produces a different list of "gaps" depending on what the model notices that day.

Two smaller items also drift the topology: `src/infrastructure/persistence/` lives outside `src/infrastructure/adapters/outbound/` (sibling tree to `clock`, `id_generator`, `query`), and the `KanbanQueryRepositoryView` adapter at `infrastructure/adapters/outbound/query/` reuses domain return types directly rather than living next to its sibling persistence concern.

The goal of this change is to make hex conformance a **terminal, mechanical** property of the project rather than an open-ended subjective review.

## Goals / Non-Goals

**Goals:**
- Eliminate Anti-Pattern 6 from the application layer by replacing the two mega input ports with one cohesive use-case class per business intent.
- Replace `KanbanError | None` domain return sentinels with typed domain exceptions raised inside aggregate methods.
- Move `src/infrastructure/persistence/` under `src/infrastructure/adapters/outbound/persistence/` so all outbound adapters share one tree, satisfying `adapter-topology-conventions` uniformly.
- Codify the entire `fastapi-hexagonal-architecture` review checklist into one architecture test suite plus tightened import-linter contracts so the conformance check becomes `pytest tests/architecture` + `lint-imports`.
- Make this change the LAST hex-related change: once the suite is green, the project is hex-conformant by definition and any drift fails CI.

**Non-Goals:**
- Adopting a module-first / bounded-contexts layout (`src/modules/kanban/{domain,application,...}`). The existing flat layout remains.
- Introducing domain events, an event bus, or async messaging.
- Splitting the single Kanban aggregate into multiple aggregates (Board, Column, Card stay one consistency boundary owned by Board).
- Replacing SQLModel with raw SQLAlchemy or another ORM.
- Adding new business features. This is a structural alignment change.
- Changing the public HTTP contract (URLs, request schemas, response schemas, error codes, status codes).

## Decisions

### Decision 1: One use-case class per business intent

Each command and query becomes a class with a single `execute()` method and explicit constructor dependencies on ports only. Replaces:

```text
KanbanCommandInputPort.handle_create_board(command)
KanbanCommandInputPort.handle_patch_board(command)
...
```

with:

```text
src/application/use_cases/board/create_board.py        → CreateBoardUseCase
src/application/use_cases/board/patch_board.py         → PatchBoardUseCase
src/application/use_cases/board/delete_board.py        → DeleteBoardUseCase
src/application/use_cases/board/get_board.py           → GetBoardUseCase
src/application/use_cases/board/list_boards.py         → ListBoardsUseCase
src/application/use_cases/column/create_column.py      → CreateColumnUseCase
src/application/use_cases/column/delete_column.py      → DeleteColumnUseCase
src/application/use_cases/card/create_card.py          → CreateCardUseCase
src/application/use_cases/card/patch_card.py           → PatchCardUseCase
src/application/use_cases/card/get_card.py             → GetCardUseCase
src/application/use_cases/health/check_readiness.py    → CheckReadinessUseCase
```

Each class:
- Constructor takes only port abstractions (`UnitOfWorkPort`, `IdGeneratorPort`, `ClockPort`, `KanbanQueryRepositoryPort`, `ReadinessProbe`).
- Exposes exactly one public method, `execute(command_or_query) -> AppResult[...]`.
- Lives in its own file named after the use case.
- Has no FastAPI imports, no SQLModel imports, no `Depends`.

**Alternatives considered:**
- Keep `handle_*` module-level functions but split the input-port interfaces. Rejected: still a god object at the dependency layer; routes still see "all commands at once"; doesn't communicate intent; doesn't fix Anti-Pattern 6.
- Use callable functions with `functools.partial` instead of classes. Rejected: harder to type, harder to mock per-use-case in tests, violates the skill's example which uses classes.

**Why classes over functions:** the skill's canonical example (`PlaceOrderUseCase`) is a class, classes pair naturally with FastAPI `Depends(...)` factories, and the constructor signature documents required ports inline.

### Decision 2: Per-route DI factories, no central handler aggregator

Each FastAPI route depends only on the use case it actually invokes:

```text
@boards_router.post("/boards")
def create_board(body, use_case: CreateBoardUseCaseDep, _: WriteApiKeyDep): ...
```

`CreateBoardUseCaseDep = Annotated[CreateBoardUseCase, Depends(get_create_board_use_case)]`

The container becomes a thin assembler that exposes per-use-case factory functions; there is no `KanbanCommandHandlers` / `KanbanQueryHandlers` aggregate. The route surfaces only the dependencies it needs, satisfying the skill's "Routes should mostly do four things" rule with maximum precision.

**Alternatives considered:**
- Single `Depends(get_use_cases)` returning a registry. Rejected: re-creates the mega object at the API boundary.
- Class-based router with use cases stored on `self`. Rejected: adds complexity for no gain; FastAPI dependency-overrides become awkward in tests.

### Decision 3: Domain exceptions replace `KanbanError | None` returns

`Board.delete_column` and `Board.move_card` currently return `KanbanError | None`. They will raise typed domain exceptions instead:

```python
class KanbanDomainError(Exception): ...
class ColumnNotFoundError(KanbanDomainError): ...
class CardNotFoundError(KanbanDomainError): ...
class InvalidCardMoveError(KanbanDomainError): ...
class EmptyPatchError(KanbanDomainError): ...   # for "no fields supplied"
```

Application use cases catch these at one place and translate to `ApplicationError` via the existing `from_domain_error` boundary, preserving the single-translation-boundary requirement from `error-boundary-and-translation`.

`KanbanError` (the existing `StrEnum`) is **kept** as the application-side discriminator (it already maps to HTTP). It stops appearing in domain return types and instead is produced by the boundary translator from the new exception classes.

`Result[Board, KanbanError]` returns from repositories also stay (those represent infrastructure-detected absence and are an outbound-adapter concern, not a domain invariant). Only domain methods change style.

**Alternatives considered:**
- Introduce a domain `Result` type and use it everywhere. Rejected: `Result` works well at port boundaries but masks invariant violations inside aggregates; the skill is explicit about raising in domain.
- Leave `KanbanError | None` returns and document them as acceptable. Rejected: this is the pattern that keeps showing up in conformance reviews.

### Decision 4: Persistence relocates under `adapters/outbound/`

```text
src/infrastructure/persistence/                          # OLD
├── sqlmodel_repository.py
├── sqlmodel_uow.py
├── sqlmodel/
│   ├── mappers.py
│   └── models/
└── lifecycle.py

src/infrastructure/adapters/outbound/persistence/        # NEW
├── sqlmodel/
│   ├── repository.py        (was sqlmodel_repository.py)
│   ├── unit_of_work.py      (was sqlmodel_uow.py)
│   ├── mappers.py
│   └── models/
└── lifecycle.py
```

The `KanbanQueryRepositoryView` adapter already lives at `adapters/outbound/query/` and stays there.

**Alternatives considered:**
- Keep `infrastructure/persistence/` as is and document it as an exception. Rejected: contradicts the existing `adapter-topology-conventions` capability that this very project codified.
- Flatten everything into `src/infrastructure/repositories/` per the skill's small-service example. Rejected: project already invested in the inbound/outbound separation; extending it is cheaper than reverting.

### Decision 5: Conformance becomes a test suite, not a checklist

A new `tests/architecture/` package (a sibling of `tests/unit/`, `tests/integration/`, `tests/e2e/`) hosts machine checks for the entire skill review checklist. The suite combines:

- **Static AST inspection tests** — walk `src/` modules and assert structural invariants (e.g., "no FastAPI route function body exceeds 12 statements", "every file in `src/application/use_cases/*` defines exactly one class whose name ends in `UseCase`", "every public method in `src/application/use_cases/*` is named `execute`").
- **Import-graph tests** — backed by `import-linter` contracts already in `pyproject.toml`, plus new contracts: forbid `src.application.contracts` imports from `src.infrastructure.adapters.outbound.persistence` (mapper isolation), forbid `pydantic.BaseModel` in `src.domain` and `src.application` (Pydantic is API-only), forbid `Depends`/`Request`/`Response` outside `src.api`.
- **Naming-convention tests** — assert ports end in `Port`, adapters end in `Adapter` or `Repository`/`View`/`UnitOfWork`, use cases end in `UseCase`, schemas live under `src.api.schemas`, mappers live under `src.api.mappers` or `src.application.contracts.mappers` or `src.infrastructure.adapters.outbound.persistence.sqlmodel.mappers`.
- **Anti-pattern guards** — tests that fail if a class in `src.application` has more than one public method (catches Anti-Pattern 6 regression), if a domain method's return type union contains an `Error` enum (catches Decision 3 regression), or if a FastAPI route imports from `src.infrastructure` directly.

Each test in the suite carries a docstring that points to the specific checklist item or skill section it enforces, so failures are self-explanatory. The suite runs in `make check` and `pre-commit`.

**Alternatives considered:**
- Lean entirely on `import-linter`. Rejected: import-linter only checks imports, not method counts, naming, or AST shape.
- Use a third-party tool like `archunit-py` or `deptry`. Rejected: adds a dependency and team-knowledge cost; AST checks with the stdlib are short and explicit.
- Generate the test suite with the LLM each time. Rejected: that is exactly the loop we are trying to break.

### Decision 6: `KanbanCommandRepositoryPort.find_by_id` returns `Board` and raises on miss

Today, `KanbanCommandRepositoryPort.find_by_id(board_id) -> Result[Board, KanbanError]` and `KanbanQueryRepositoryPort.find_by_id(board_id) -> Result[Board, KanbanError]` are duplicated. To keep the boundary clean and consistent with Decision 3, command-side load methods will raise an outbound-adapter exception (`BoardNotFoundError`, an infrastructure-side exception in the persistence adapter) and the use case translates it. The query-side `find_by_id` keeps the `Result` shape because read models are explicitly nullable contracts. This makes command flow read like `board = uow.commands.load_board(board_id)` instead of `match`-on-`Result`.

**Alternatives considered:**
- Keep both as `Result`. Rejected: the command path is then forced to use `Err`-aware code paths inside use cases, which the skill discourages ("application layer should contain orchestration, not low-level infrastructure").
- Make both raise. Rejected: query handlers genuinely need explicit "missing" semantics for HTTP 404 on `GET /boards/{id}`.

## Risks / Trade-offs

- **Risk: large blast radius across application layer and tests** → Mitigation: split tasks per aggregate (board, column, card, health) and run the full test suite after each aggregate is migrated; the new architecture suite catches regressions immediately.
- **Risk: per-route DI explodes the dependencies module** → Mitigation: `src/api/dependencies.py` is split into `src/api/dependencies/__init__.py` re-exports plus `src/api/dependencies/use_cases.py`, `src/api/dependencies/security.py`, etc. Dependency factory functions stay short (~3 lines each).
- **Risk: behavior drift while moving from sentinels to exceptions** → Mitigation: the new exceptions are translated by the same `from_domain_error` table; the existing API integration tests are unchanged and pass after the refactor as the contract observability gate.
- **Risk: architecture suite becomes brittle and over-fits the current code** → Mitigation: each test asserts a normative rule cited by spec capability + line in the skill, not the existence of specific files; tests use module-glob discovery so adding a new use case doesn't require updating them.
- **Trade-off: more files** → The application layer grows from 3 handler aggregator files to ~11 use-case files. This is the explicit shape the skill prescribes and is the price of intention-revealing names.
- **Trade-off: persistence path changes break any third-party consumer** → Acceptable: this is a private starter template; the change is scoped to one repo and is documented as a **BREAKING** in the proposal.

## Migration Plan

1. **Phase 0 — Add architecture test scaffolding (no behavior change).** Create `tests/architecture/__init__.py`, `tests/architecture/test_hex_conformance.py` with the test cases that already pass on the current code (dependency direction, no-FastAPI-in-domain, etc.). Wire into `make check` and `pre-commit`. This anchors the suite before the refactor.
2. **Phase 1 — Domain exception migration.** Add domain exception classes, update `Board.delete_column` and `Board.move_card` to raise, update the two affected use cases (`handle_delete_column`, `handle_patch_card`/`handle_create_card`) to catch, update unit tests. Run full test suite. Add architecture test asserting "no domain method's return type is `<X> | None` where `<X>` is an `Enum` subclass".
3. **Phase 2 — Persistence relocation.** Move files from `src/infrastructure/persistence/` to `src/infrastructure/adapters/outbound/persistence/`. Update `import-linter` contracts and `composition.py` imports. Run full test suite.
4. **Phase 3 — Use-case decomposition (board aggregate).** Create `src/application/use_cases/board/{create,patch,delete,get,list}_board.py` with one class each. Update DI factories. Update `boards_router`. Delete the corresponding `handle_*_board` functions and their entries in `KanbanCommandHandlers` / `KanbanQueryHandlers`. Run full test suite.
5. **Phase 4 — Use-case decomposition (column, card, health aggregates).** Repeat phase 3 per aggregate. After this phase, `KanbanCommandHandlers`, `KanbanQueryHandlers`, `KanbanCommandInputPort`, `KanbanQueryInputPort` are deleted entirely.
6. **Phase 5 — Conformance suite hardening.** Add the remaining architecture tests that would have failed before phases 1–4 (single-method-per-use-case, no-mega-port, no-Pydantic-in-domain, no-Depends-in-application, etc.). Confirm all are green.
7. **Phase 6 — Update import-linter contracts and docs.** Tighten `pyproject.toml` contracts, update `hex-design-guide.md` with the new shape, archive the change.

Rollback: each phase is a single commit on a feature branch; reverting a phase is a clean `git revert`. The architecture suite is additive and can be disabled by removing the `tests/architecture/` directory.

## Open Questions

- None blocking. Health-check uses (`KanbanQueryHandlers.handle_health_check` + `ReadinessProbe`) cleanly map to a `CheckReadinessUseCase`; the only design choice is keeping it under `use_cases/health/` vs. a top-level `system` aggregate — this design picks `health/` for symmetry.
