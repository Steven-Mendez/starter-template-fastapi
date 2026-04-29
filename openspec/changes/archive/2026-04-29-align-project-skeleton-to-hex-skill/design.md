## Context

`./.opencode/skills/fastapi-hexagonal-architecture/SKILL.md` defines the canonical
shape of a hexagonal FastAPI service. The codebase already enforces every dynamic
constraint of that skill via `tests/architecture/` (15 passing tests) and
`pyproject.toml` import-linter contracts (6 kept, 0 broken). What remains are
three structural / dead-surface deviations that contradict the skill's literal
text:

- Skill section "main.py" places the FastAPI app at `src/main.py`. Project has
  `./main.py` and a workaround `pythonpath = ["."]` in `pyproject.toml`.
- Skill section "Configuration" places `BaseSettings` at
  `src/infrastructure/config.py`. Project has `src/config/settings.py`, an
  out-of-taxonomy package that the import-linter has to list explicitly in
  `forbidden_modules` for both Domain and Application contracts.
- Skill section "Ports" recommends declaring only what application needs.
  `src/application/ports/kanban_repository.py` declares an aggregator Protocol
  (`KanbanRepositoryPort`) that no module under `src/application/` imports;
  it exists only as a convenience type in infrastructure and tests.

This change moves the skeleton into compliance and locks the third decision in
place with a new architecture test.

## Goals / Non-Goals

**Goals:**
- Move the FastAPI entrypoint to `src/main.py`.
- Move `AppSettings` into `src/infrastructure/config/settings.py` and remove
  `src/config/`.
- Remove the `KanbanRepositoryPort` aggregator from
  `src/application/ports/` and adjust infrastructure consumers to compose the
  three segregated ports directly.
- Add an architecture test that prevents reintroducing repository aggregator
  ports in `src/application/ports/`.
- Keep all existing tests (`unit`, `integration`, `e2e`, `architecture`) green
  with no behaviour changes.

**Non-Goals:**
- Refactoring use cases, domain logic, or application contracts.
- Touching the HTTP API, OpenAPI surface, database schema, or migrations.
- Reorganising `tests/` beyond the minimal updates required by the moves.
- Splitting or merging the existing C/Q/Lookup repository ports.
- Changing the read-model adapter (`KanbanQueryRepositoryView`).

## Decisions

### D1 — Move `main.py` into `src/`

Move `./main.py` to `src/main.py`. Update `pyproject.toml` to remove
`pythonpath = ["."]` (or replace with `pythonpath = ["src"]` only if needed for
test collection — verify by running the existing test matrix).

Update every operator-facing entrypoint:

- `Dockerfile`: change `CMD`/`ENTRYPOINT` from `uvicorn main:app` to
  `uvicorn src.main:app`.
- `docker-compose.yml`: same uvicorn invocation.
- `Makefile`: any `dev`/`run` target referencing `main:app`.
- `README.md`: usage examples.
- CI workflows under `.github/workflows/` if they invoke uvicorn explicitly.
- `alembic/env.py`: only update if it imports from the old location (likely
  not — it usually imports `src.infrastructure...`).

**Alternatives considered:** keeping `./main.py` and documenting it as an
intentional shortcut. Rejected because the skill text is explicit about the
location and because keeping it forces a `pythonpath` workaround.

### D2 — Relocate settings into infrastructure

Move `src/config/settings.py` → `src/infrastructure/config/settings.py`.
Delete `src/config/` entirely (including `__init__.py`).

Update import sites:

- `src/api/dependencies/security.py`
- `src/infrastructure/config/di/composition.py`
- `src/infrastructure/config/di/container.py`
- `src/main.py` (after D1)
- Any test or alembic module importing `src.config.settings`.

Update `pyproject.toml` import-linter contracts:

- "Domain layer: no outward or framework dependencies" → remove `"src.config"`
  from `forbidden_modules`.
- "Application layer: no infrastructure or framework dependencies" → remove
  `"src.config"` from `forbidden_modules` (settings will then live under
  `src.infrastructure`, which is already forbidden).

`src/infrastructure/config/__init__.py` may re-export `AppSettings` and
`get_settings` for ergonomics, or callers can import directly from
`src.infrastructure.config.settings` — pick one consistent style at
implementation time.

**Alternatives considered:**

- Keep settings at `src/config/`, document the deviation. Rejected — contradicts
  skill text and clutters import-linter config.
- Place settings at `src/infrastructure/config.py` (single file, exact skill
  layout). Rejected because `src/infrastructure/config/` is already a package
  housing `di/`. A `settings.py` module inside that package is the natural fit.

### D3 — Remove the `KanbanRepositoryPort` aggregator

Delete `src/application/ports/kanban_repository.py` and remove
`KanbanRepositoryPort` from `src/application/ports/__init__.py` (`__all__` and
imports).

In `src/infrastructure/adapters/outbound/persistence/sqlmodel/repository.py`,
change `_BaseSQLModelKanbanRepository(KanbanRepositoryPort)` to inherit
explicitly from the three segregated ports:

```python
class _BaseSQLModelKanbanRepository(
    KanbanQueryRepositoryPort,
    KanbanCommandRepositoryPort,
    KanbanLookupRepositoryPort,
):
    ...
```

In `src/infrastructure/config/di/composition.py`, redefine
`ManagedKanbanRepositoryPort` to compose the three segregated ports directly
(plus `ReadinessProbe` and `ClosableResource`):

```python
class ManagedKanbanRepositoryPort(
    KanbanQueryRepositoryPort,
    KanbanCommandRepositoryPort,
    KanbanLookupRepositoryPort,
    ReadinessProbe,
    ClosableResource,
    Protocol,
):
    pass
```

This keeps `ManagedKanbanRepositoryPort` (which is *infrastructure-side*, not
in `src/application/ports/`) as the single composite type used by the DI
container, while the application layer only sees segregated ports.

Update `tests/unit/test_hexagonal_boundaries.py` to drop any reference to
`KanbanRepositoryPort`.

**Alternatives considered:**

- Keep the aggregator and treat it as a convenience type. Rejected because it
  lives in `src/application/ports/` and no application module consumes it →
  dead surface in the layer that defines what application needs.
- Move the aggregator into `src/infrastructure/`. Rejected — it would be a
  duplicate of `ManagedKanbanRepositoryPort`.

### D4 — Add architecture test to forbid future aggregators

Add `tests/architecture/test_no_repository_aggregator_ports.py` (marker:
`@pytest.mark.architecture`). The test walks every module under
`src.application.ports` (using `iter_python_modules` from
`tests/architecture/conftest.py`), inspects each `ClassDef` that is a
`Protocol`, and fails if it inherits from more than one class whose name ends
in `RepositoryPort`. This complements the existing
`test_no_aggregator_ports.py` (which targets `handle_*` aggregations and
specific forbidden symbol names) by closing the repository-aggregation gap.

**Alternatives considered:**

- Extend `test_no_aggregator_ports.py` instead of adding a new file. Either is
  fine — pick whichever keeps each test file's intent narrow at implementation
  time. The spec only requires the rule to exist somewhere under
  `tests/architecture/` with the `architecture` marker.

## Risks / Trade-offs

- **[Risk] Operator scripts hard-coded to `uvicorn main:app` break after D1.**
  → Mitigation: announce the change in `README.md` deployment section, update
  `Dockerfile`, `docker-compose.yml`, and CI in the same PR, and call this out
  as **BREAKING** in the proposal.
- **[Risk] Alembic env / migrations rely on `src.config.settings` import path.**
  → Mitigation: implementation step explicitly greps for `src.config` across
  the repo and updates every match in the same change.
- **[Risk] An external consumer imports `KanbanRepositoryPort`.**
  → Mitigation: the symbol is internal to this repository (no public package
  surface). A repo-wide grep before deletion confirms only `src/infrastructure/`
  and tests consume it.
- **[Trade-off] D2 places settings in a package (`infrastructure/config/`)
  rather than the single-file `infrastructure/config.py` shown in the skill.**
  This is a minor structural deviation already imposed by the existing `di/`
  subpackage; we accept it because merging `di/` and settings into a single
  module would be a larger, unrelated refactor.

## Migration Plan

1. Land D1 (move `main.py`) and D2 (move settings) together — both are pure
   relocations and share entrypoint updates (`Dockerfile`, `Makefile`,
   `docker-compose.yml`, `pyproject.toml`).
2. Land D3 + D4 (drop aggregator + add test) in the same step. The new
   architecture test must be green before the aggregator deletion is committed.
3. Run the full test matrix locally:
   - `uv run pytest tests/architecture -m architecture`
   - `uv run lint-imports`
   - `uv run pytest tests/unit`
   - `uv run pytest tests/integration` (testcontainers)
   - `uv run pytest tests/e2e`
4. Smoke-test `uvicorn src.main:app` and the docker-compose stack.

**Rollback:** revert the change PR. No data or schema migrations are involved,
so rollback is purely code-level.

## Open Questions

- Should `src/infrastructure/config/__init__.py` re-export `AppSettings` and
  `get_settings`, or should callers import from
  `src.infrastructure.config.settings` directly? Decide at implementation
  time based on the diff size.
- Should `pyproject.toml` `pythonpath` become `["src"]` after D1, or be
  removed entirely? Verify by running `pytest` after the move.
