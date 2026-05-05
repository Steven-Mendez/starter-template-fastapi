## Context

The template currently uses layer-first organization (`src/{api,application,domain,infrastructure}`). This made sense when there was a single bounded context, but the project's purpose is to be cloned by users who will add new business features. Today, adding a feature requires touching four sibling directories and there is no obvious "boundary" of where a feature begins and ends. The hexagonal-architecture skill recommends feature-first layout for exactly this reason: each feature is a self-contained vertical slice owning its domain, application, ports and adapters; only truly cross-cutting concerns (settings, framework wiring, shared kernel) live in a separate platform package.

Constraints:

- The HTTP surface is in production-style use; payload and status codes must not change.
- Import-linter is the conformance gate (`make lint-arch`); after the move it must continue to fail-closed on boundary violations.
- mypy strict mode (`disallow_untyped_defs`) must keep passing.
- Alembic migrations must keep working without rewriting history.

## Goals / Non-Goals

**Goals:**

- One canonical filesystem layout that any future feature will follow without ambiguity.
- Kanban becomes the reference implementation: every file in it serves as a "what good looks like" example.
- Inbound and outbound ports both expressed as Protocols inside the feature; HTTP adapter depends on inbound Protocols.
- Platform code is feature-agnostic: nothing in `src/platform/` may import from `src/features/*`.
- Conformance contracts continue to enforce hex direction and add cross-feature isolation.
- Apply FastAPI idioms (return types over `response_model`, router-level deps, single tagging, `fastapi` CLI entrypoint).
- Zero runtime behavior change for the HTTP API.

**Non-Goals:**

- Adding tests (handled by a separate change `testing-suite-foundation`).
- Adding documentation/guides (handled by a separate change `feature-template-and-docs`).
- Migrating to async persistence or rewriting Problem+JSON.
- Changing alembic revision history.
- Replacing pydantic-settings, SQLModel, psycopg.

## Decisions

### D1. Feature-first layout with separate platform package

```text
src/
  main.py
  platform/
    config/settings.py
    api/
      app_factory.py            # create_app() lives here
      error_handlers.py         # Problem+JSON
      middleware/request_context.py
      dependencies/
        container.py            # set_app_container, get_app_container
        security.py             # require_write_api_key
    persistence/
      sqlmodel/
        engine.py
        lifecycle.py
      readiness.py
    shared/
      result.py
      clock_port.py
      id_generator_port.py
      adapters/
        system_clock.py
        uuid_id_generator.py
  features/
    kanban/
      domain/
        models/{board,column,card,card_priority,board_summary}.py
        specifications/card_move.py
        errors.py
      application/
        ports/
          inbound/{create_board,patch_board,delete_board,get_board,
                   list_boards,create_column,delete_column,
                   create_card,patch_card,get_card,check_readiness}.py
          outbound/{kanban_command_repository,kanban_lookup_repository,
                    kanban_query_repository,unit_of_work}.py
        commands/{board,column,card}.py
        queries/{board,card,health}.py
        contracts/{kanban,mappers}.py
        errors.py
        use_cases/
          board/, column/, card/, health/
      adapters/
        inbound/
          http/
            router.py
            boards.py columns.py cards.py health.py
            schemas/, mappers/, errors.py
        outbound/
          persistence/sqlmodel/{models/,repository.py,unit_of_work.py,mappers.py}
          query/kanban_query_repository_view.py
      composition/
        container.py             # KanbanContainer factory
        wiring.py                # register_kanban(app, platform)
```

**Alternatives considered:**

- *Layer-first kept (status quo)*: rejected — does not match the template's purpose.
- *Hybrid (capas globales con subcarpetas por feature)*: rejected — the user explicitly chose full feature-first; hybrid keeps cross-cutting hops between sibling capas.

### D2. Inbound ports as `Protocol`-per-use-case

Each use case has a Protocol in `application/ports/inbound/<verb>_<noun>.py`. Naming: `<UseCase>UseCasePort` (e.g., `CreateBoardUseCasePort`). The HTTP adapter parameter type is the Protocol. The composition root binds the Protocol to the concrete class.

**Alternatives considered:**

- *Single fat inbound port per feature*: rejected — couples unrelated operations and breaks Interface Segregation.
- *No inbound ports (status quo)*: rejected — the skill's checklist explicitly requires it.

### D3. Composition root per feature

Each feature owns its `composition/wiring.py` with a public function `register_<feature>(app: FastAPI, platform: PlatformContainer) -> None`. `src/main.py` builds the platform once and calls `register_kanban(app, platform)`. This keeps wiring local and makes adding/removing a feature a one-line change in `main.py`.

### D4. Platform shared kernel boundary

`src/platform/shared/` holds only truly cross-cutting abstractions: `Result`, `ClockPort`, `IdGeneratorPort`, plus their default adapters. Domain-specific ports (Kanban repositories) stay inside `features/kanban/application/ports/outbound/`.

### D5. Import-linter rewrite (per-feature contracts)

Replace the current global contracts with per-feature templates. For each feature `F`:

- `F.domain` MUST NOT import `F.application`, `F.adapters`, any framework, or any other feature.
- `F.application` MUST NOT import `F.adapters`, `src.platform.api`, `src.platform.persistence`, FastAPI, SQLModel/SQLAlchemy, Alembic, psycopg.
- `F.adapters.inbound` MUST NOT import `F.adapters.outbound` directly nor `F.domain` directly (must go through application).
- `F.adapters.outbound` MUST NOT import `F.adapters.inbound` nor `F.application.use_cases` nor `F.application.ports.inbound`.
- `src.platform` MUST NOT import `src.features.*`.
- Cross-feature imports forbidden: `src.features.kanban` MUST NOT import any other `src.features.*`.
- Layer global: `features.*.adapters → features.*.application → features.*.domain`.

### D6. FastAPI idioms applied during the move

- Drop `response_model=` whenever the function return type already declares it.
- Per-router split for writes: `boards_write_router = APIRouter(dependencies=[Depends(require_write_api_key)])`; `boards_read_router = APIRouter()`; both included into `boards_router`.
- `kanban_router` keeps `prefix="/api"` but loses `tags=["kanban"]` to avoid double-tagging.
- Add `[tool.fastapi] entrypoint = "src.main:app"`. `Makefile.dev` → `fastapi dev`. `Dockerfile.CMD` → `fastapi run`.
- Type the API container settings exposure as `AppSettings` (no `Any`).
- Move `get_app_container` to `platform.api.dependencies.container`.

### D7. Strangler-style move, not rewrite

Files are moved with their content intact wherever possible; only imports and a few names change. Behavior preservation verified by running `make check` (ruff + mypy + import-linter) at every step. No tests yet exist, so behavior is verified manually with `fastapi dev` + `curl` smoke checks documented in tasks.

### D8. Alembic remains pointed at the new metadata path

`alembic/env.py` will import `target_metadata` from `src.features.kanban.adapters.outbound.persistence.sqlmodel.models.metadata` (or the new equivalent). Migration files are not edited.

## Risks / Trade-offs

- **[Risk] Massive diff is hard to review** → Mitigation: tasks split the move into platform-first, then kanban-domain, then kanban-application, then kanban-adapters, with `make check` green between steps. Use `git mv` so history is preserved.
- **[Risk] Hidden import cycles after the move** → Mitigation: rebuild import-linter contracts before the move; run them after each step.
- **[Risk] Alembic autogenerate drift if metadata import path is wrong** → Mitigation: run `uv run alembic upgrade head` and `uv run alembic check` after the move; document the metadata path explicitly in `env.py`.
- **[Risk] FastAPI `[tool.fastapi]` entrypoint breaks `uvicorn` users** → Mitigation: keep `uvicorn` in `dependencies`; document both invocations in the README.
- **[Trade-off] Co-located feature complicates packaging** → Accepted: this is a template, not a published library; if/when published, the wheel build excludes feature-private modules already.
- **[Risk] Inbound Protocols add boilerplate** → Accepted: the cost is one tiny file per use case; the benefit is correct dependency direction and easier mocking.

## Migration Plan

1. Add new import-linter contracts side-by-side, scoped to currently empty `src.features.*` and `src.platform.*` namespaces (no-ops at first).
2. Create `src/platform/` and move shared infrastructure (settings, app factory, middleware, error handlers, shared kernel ports/adapters, persistence engine). Update `src/main.py` and run `make check`.
3. Create `src/features/kanban/` and move domain (`git mv src/domain/kanban → src/features/kanban/domain`, plus `src/domain/shared` content into `src/platform/shared`). Update imports. `make check`.
4. Move application layer (ports, commands, queries, contracts, errors, use_cases) into `src/features/kanban/application/`. Add inbound port Protocols. `make check`.
5. Move adapters: HTTP into `adapters/inbound/http/`, persistence + query into `adapters/outbound/`. Apply FastAPI idioms (response_model cleanup, write router split, single tagging). `make check`.
6. Add `composition/wiring.py` and reduce `src/main.py` to platform build + `register_kanban`.
7. Switch `pyproject.toml` import-linter contracts from old layout to per-feature contracts; remove the legacy global ones. `make lint-arch`.
8. Add `[tool.fastapi] entrypoint`, switch `Makefile` and `Dockerfile`. Smoke-test with `fastapi dev` and `curl`.
9. Update `alembic/env.py` metadata import.
10. Add migration note to `README.md`.

Rollback: revert the merge commit; the legacy directories are removed atomically only at the end, allowing partial reverts during review.

## Open Questions

- Should `Result/Ok/Err` live in `src/platform/shared/result.py` or be re-exported from a deeper namespace? (Lean: `platform/shared/result.py`.)
- Should we provide a deprecation shim re-exporting old paths for one minor version? (Lean: no — this is a template, not a library; downstream users follow a README migration note.)
