## Why

Even after four hex-architecture changes have been archived, every new conformance review keeps surfacing "gaps". The root cause is structural: (1) the application layer still exposes generic mega input ports (`KanbanCommandInputPort`, `KanbanQueryInputPort`) which trigger Anti-Pattern 6 from `fastapi-hexagonal-architecture` ("Generic service objects with too many methods"), (2) business intents are encoded as procedural `handle_*` functions instead of intention-revealing use-case classes, (3) the hex skill's 17-item review checklist is enforced subjectively per review instead of by automated guards, and (4) the domain layer still mixes `KanbanError | None` return-sentinel style with raised exceptions, blurring the domain boundary. This change is the definitive alignment pass: it codifies conformance into mechanical checks and removes the remaining structural anti-patterns so the review loop ends.

## What Changes

- Replace `KanbanCommandInputPort` and `KanbanQueryInputPort` mega input ports with per-use-case classes. Each business intent is a single cohesive class (e.g., `CreateBoardUseCase`, `PatchCardUseCase`, `GetBoardQueryHandler`) with one `execute()` method and explicit constructor dependencies on ports only.
- Wire each FastAPI route to its specific use case via `Depends(get_<use_case>)` factories so routes never reach into a god-object.
- Migrate domain methods that return `KanbanError | None` (`Board.delete_column`, `Board.move_card`) to raise typed domain exceptions (`ColumnNotFoundError`, `InvalidCardMoveError`, `CardNotFoundError`). Application layer translates these to `ApplicationError` at a single boundary.
- Move `src/infrastructure/persistence/` under `src/infrastructure/adapters/outbound/persistence/` so adapter topology is uniform (currently persistence sits outside the `adapters/outbound/` tree, contradicting the existing `adapter-topology-conventions` capability).
- Codify the entire `fastapi-hexagonal-architecture` review checklist into a single automated `tests/architecture/test_hex_conformance.py` suite plus tightened `import-linter` contracts, so future "are we hexagonal?" checks become a `make check` call instead of an LLM review.
- **BREAKING**: Public application-side import paths change (`from src.application.commands import KanbanCommandHandlers` is removed). Inbound adapters and tests must import per-use-case classes.
- **BREAKING**: Domain methods on `Board` no longer return `KanbanError | None`; callers must handle raised domain exceptions.
- **BREAKING**: Infrastructure import paths change due to the persistence module move.

## Capabilities

### New Capabilities
- `hexagonal-architecture-conformance`: Codify the `fastapi-hexagonal-architecture` skill's review checklist as machine-verifiable, CI-enforced requirements (import boundaries, naming, dependency direction, mapper isolation, port cohesion, error placement) so conformance regressions surface as test failures, not human reviews.
- `use-case-cohesion`: Define per-use-case class structure, intention-revealing naming, and per-route dependency injection rules that eliminate generic mega input ports from the application layer.

### Modified Capabilities
- `adapter-topology-conventions`: Tighten outbound topology to require all outbound adapters (including persistence) to live under `src/infrastructure/adapters/outbound/<concern>/` and forbid sibling outbound trees outside `adapters/outbound/`.
- `error-boundary-and-translation`: Require domain rule violations to be expressed as typed domain exceptions; sentinel-return style (`Error | None`, `Result[T, KanbanError]` for invariant violations) is non-conformant in the domain layer.

## Impact

- Affected code: every application command/query handler, every API route, the DI container/composition module, the persistence module path, and `Board` domain methods.
- Affected tests: unit tests targeting `KanbanCommandHandlers`/`KanbanQueryHandlers` are replaced with per-use-case unit tests; new architecture suite is added.
- Affected tooling: `pyproject.toml` `[tool.importlinter]` contracts gain stricter rules; new `tests/architecture/` test target is wired into `make check` and `pre-commit`.
- Affected docs: `hex-design-guide.md` and the `fastapi-hexagonal-architecture` skill are referenced directly from the conformance test docstrings so the source of truth is single.
- Long-term effect: the iterative "find-the-gap" review loop is replaced by a deterministic, testable gate. Once the suite is green, the project is hex-conformant by definition; future drift fails CI.
